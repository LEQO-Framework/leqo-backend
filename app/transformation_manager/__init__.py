"""
Provides the core logic of the backend.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Annotated, Any, Literal, cast

from fastapi import Depends
from networkx.algorithms.dag import topological_sort
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.config import Settings
from app.enricher import Constraints, Enricher, ParsedImplementationNode
from app.model.CompileRequest import (
    ArrayLiteralNode,
    BitLiteralNode,
    BoolLiteralNode,
    CompileRequest,
    EncodeValueNode,
    FloatLiteralNode,
    IfThenElseNode,
    ImplementationNode,
    InsertRequest,
    IntLiteralNode,
    NestedBlock,
    OptimizeSettings,
    RepeatNode,
    SingleInsert,
)
from app.model.CompileRequest import Node as FrontendNode
from app.model.data_types import IntType, LeqoSupportedType
from app.openqasm3.printer import leqo_dumps
from app.services import get_db_engine, get_enricher, get_settings
from app.transformation_manager.frontend_graph import FrontendGraph
from app.transformation_manager.graph import (
    ClassicalIOInstance,
    IOConnection,
    ProcessedProgramNode,
    ProgramGraph,
    ProgramNode,
)
from app.transformation_manager.merge import merge_nodes
from app.transformation_manager.nested.if_then_else import enrich_if_then_else
from app.transformation_manager.nested.repeat import unroll_repeat
from app.transformation_manager.nested.utils import generate_pass_node_implementation
from app.transformation_manager.optimize import optimize
from app.transformation_manager.post import postprocess
from app.transformation_manager.pre import preprocess
from app.transformation_manager.pre.utils import PreprocessingException
from app.utils import not_none
import xml.etree.ElementTree as ET
import xml.etree.ElementTree as ET
from typing import Iterable, Dict, Tuple
import uuid
import random
import string

TLookup = dict[str, tuple[ProgramNode, FrontendNode]]


class CommonProcessor:
    """
    Process a :class:`~app.transformation_manager.frontend_graph.FrontendGraph`.

    :param enricher: The enricher to use to get node implementations
    :frontend_graph: The graph to process
    :optimize_settings: Specify how to optimize the result
    """

    frontend_graph: FrontendGraph
    graph: ProgramGraph
    enricher: Enricher
    optimize: OptimizeSettings
    frontend_to_processed: dict[str, ProcessedProgramNode]
    target: Literal["qasm", "workflow"] = "qasm"
    original_request: CompileRequest | None = None
    result: str | None = None
    qrms: Any | None = None
    service_deployment_models: Any | None = None

    def __init__(
        self,
        enricher: Enricher,
        frontend_graph: FrontendGraph,
        optimize_settings: OptimizeSettings,
        qiskit_compat: bool = False,
        result: str | None = None,
    ) -> None:
        self.enricher = enricher
        self.frontend_graph = frontend_graph
        self.optimize = optimize_settings
        self.graph = ProgramGraph()
        self.frontend_to_processed = {}
        self.qiskit_compat = qiskit_compat
        self.result = result
        self.qrms = None
        self.service_deployment_models = None

    def _resolve_inputs(
        self,
        target_node: str,
        frontend_name_to_index: dict[str, int] | None = None,
    ) -> tuple[dict[int, LeqoSupportedType], dict[int, Any]]:
        """
        Get inputs of current node from previous processed nodes.
        """
        target_frontend_node = self.frontend_graph.node_data[target_node]
        requested_inputs: dict[int, LeqoSupportedType] = {}
        requested_values: dict[int, Any] = {}
        for source_node in self.frontend_graph.predecessors(target_node):
            source_node_data = not_none(
                self.frontend_to_processed.get(source_node),
                f"Node '{source_node}' should already be enriched",
            )
            source_frontend_node = self.frontend_graph.node_data[source_node]

            for edge in not_none(
                self.frontend_graph.edge_data.get((source_node, target_node)),
                "Edge should exist",
            ):
                output_index = edge.source[1]
                output = source_node_data.io.outputs.get(output_index)
                if output is None:  # https://github.com/python/mypy/issues/17383
                    msg = f"Node '{source_node}' does not define an output with index {output_index}"
                    node = self.frontend_graph.node_data[source_node]
                    raise PreprocessingException(
                        msg,
                        None if isinstance(node, ParsedImplementationNode) else node,
                    )

                input_index = edge.target[1]
                constant_value = self._extract_literal_value(
                    source_frontend_node, output_index
                )

                requested_type = output.type
                if (
                    isinstance(target_frontend_node, EncodeValueNode)
                    and target_frontend_node.encoding == "basis"
                    and isinstance(output, ClassicalIOInstance)
                    and isinstance(output.type, IntType)
                    and isinstance(source_frontend_node, IntLiteralNode)
                    and "bitSize" not in source_frontend_node.model_fields_set
                    and isinstance(constant_value, int)
                ):
                    inferred_size = self._infer_literal_bitsize(constant_value)
                    current_int_type = cast(IntType, requested_type)
                    if inferred_size < current_int_type.size:
                        requested_type = IntType.with_size(inferred_size)

                requested_inputs[input_index] = requested_type

                if constant_value is not None:
                    requested_values[input_index] = constant_value

                if edge.identifier is None or frontend_name_to_index is None:
                    continue

                frontend_name_to_index[edge.identifier] = input_index

        return requested_inputs, requested_values

    @staticmethod
    def _infer_literal_bitsize(value: int) -> int:
        """
        Derive the minimal two's-complement bit width required to represent value.
        """
        if value >= 0:
            return max(1, value.bit_length())
        return max(1, (-value - 1).bit_length() + 1)

    @staticmethod
    def _extract_literal_value(
        node: FrontendNode | ParsedImplementationNode, output_index: int
    ) -> Any | None:
        """
        Try to resolve a literal value flowing from the given node.
        """
        if output_index != 0:
            return None

        literal_value: Any | None
        match node:
            case ArrayLiteralNode(values=values):
                literal_value = values
            case IntLiteralNode(value=value):
                literal_value = value
            case BitLiteralNode(value=value):
                literal_value = int(value)
            case BoolLiteralNode(value=value):
                literal_value = value
            case FloatLiteralNode(value=value):
                literal_value = value
            case _:
                literal_value = None

        return literal_value


class MergingProcessor(CommonProcessor):
    """
    Process request with the whole pipeline.
    """

    @staticmethod
    def from_compile_request(
        request: CompileRequest,
        enricher: Annotated[Enricher, Depends(get_enricher)],
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> MergingProcessor:
        graph = FrontendGraph.create(request.nodes, request.edges)
        processor = MergingProcessor(
            enricher,
            graph,
            request.metadata,
            qiskit_compat=settings.qiskit_compat_mode,
        )
        processor.target = request.compilation_target
        processor.original_request = request
        processor.qrms = request.qrms
        processor.service_deployment_models = request.serviceDeploymentModels
        return processor

    async def process_nodes(self) -> None:
        """
        Process graph by enriching and preprocessing the nodes.
        """
        for node in topological_sort(self.frontend_graph):
            frontend_node = self.frontend_graph.node_data[node]

            missing_constant_inputs: set[int] = set()

            if isinstance(frontend_node, RepeatNode):
                requested_inputs, _ = self._resolve_inputs(node)
                entry_node_id, exit_node_id, enrolled_graph = unroll_repeat(
                    frontend_node,
                    requested_inputs,
                )
                sub_graph = await self._build_inner_graph(enrolled_graph)
                processed_node = sub_graph.node_data[ProgramNode(entry_node_id)]
                exit_node = sub_graph.node_data[ProgramNode(exit_node_id)]
                for n in sub_graph.nodes:
                    self.graph.append_node(sub_graph.node_data[n])
                for e in sub_graph.edges:
                    self.graph.append_edges(*sub_graph.edge_data[e])
                self.frontend_to_processed[node] = exit_node
            else:
                requested_values: dict[int, Any]
                if isinstance(frontend_node, IfThenElseNode):
                    frontend_name_to_index: dict[str, int] = {}
                    requested_inputs, requested_values = self._resolve_inputs(
                        node, frontend_name_to_index
                    )
                    enriched_node: (
                        ImplementationNode | ParsedImplementationNode
                    ) = await enrich_if_then_else(
                        frontend_node,
                        requested_inputs,
                        frontend_name_to_index,
                        self._build_inner_graph,
                    )
                else:
                    requested_inputs, requested_values = self._resolve_inputs(node)
                    enriched_node = await self.enricher.enrich(
                        frontend_node,
                        Constraints(
                            requested_inputs=requested_inputs,
                            optimizeWidth=self.optimize.optimizeWidth is not None,
                            optimizeDepth=self.optimize.optimizeDepth is not None,
                            requested_input_values=requested_values,
                        ),
                    )
                processed_node = preprocess(
                    ProgramNode(node),
                    enriched_node.implementation,
                    requested_inputs,
                )
                if isinstance(frontend_node, EncodeValueNode) and requested_values:
                    missing_constant_inputs = {
                        index
                        for index in requested_values
                        if index not in processed_node.io.inputs
                    }
                else:
                    missing_constant_inputs = set()
                self.frontend_to_processed[node] = processed_node
                self.graph.append_node(processed_node)

            for pred in self.frontend_graph.predecessors(node):
                for edge in self.frontend_graph.edge_data[(pred, node)]:
                    if edge.target[1] in missing_constant_inputs:
                        continue
                    self.graph.append_edge(
                        IOConnection(
                            (
                                self.frontend_to_processed[edge.source[0]].raw,
                                edge.source[1],
                            ),
                            (processed_node.raw, edge.target[1]),
                            edge.identifier,
                            edge.size,
                        )
                    )

    async def _build_inner_graph(self, frontend_graph: FrontendGraph) -> ProgramGraph:
        """
        Convert :class:`~app.transformation_manager.frontend_graph.FrontendGraph` to :class:`~app.transformation_manager.graph.ProgramGraph`.

        This is used as dependency injection for nested nodes.

        :param frontend_graph: The graph to transform
        :return: the enriched + preprocessed graph
        """
        processor = MergingProcessor(
            self.enricher,
            frontend_graph,
            self.optimize,
            qiskit_compat=self.qiskit_compat,
        )
        await processor.process_nodes()

        if self.optimize.optimizeWidth is not None:
            optimize(self.graph)

        return processor.graph

    def _collect_literal_nodes(self) -> tuple[set[str], set[str]]:
        literal_ids = {
            node_id
            for node_id, frontend_node in self.frontend_graph.node_data.items()
            if isinstance(
                frontend_node,
                IntLiteralNode
                | FloatLiteralNode
                | BitLiteralNode
                | BoolLiteralNode
                | ArrayLiteralNode,
            )
        }
        used_ids: set[str] = set()
        for (source, _target), edges in self.frontend_graph.edge_data.items():
            if source in literal_ids and edges:
                used_ids.add(source)
        return literal_ids, used_ids

    async def process(self) -> str:
        """
        Process the :class:`~app.model.CompileRequest`.

        #. Enrich frontend nodes.
        #. :meth:`~app.transformation_manager.pre.preprocess` frontend nodes.
        #. Optionally :meth:`~app.transformation_manager.optimize.optimize` graph width.
        #. :meth:`~app.transformation_manager.merge.merge_nodes` and
        #. :meth:`~app.transformation_manager.post.postprocess` into final program.

        :return: The final QASM program as a string.
        """
        await self.process_nodes()

        if self.optimize.optimizeWidth is not None:
            optimize(self.graph)

        literal_nodes: set[str]
        used_literal_nodes: set[str]
        #if self.qiskit_compat and self.target == "qasm":
        literal_nodes, used_literal_nodes = self._collect_literal_nodes()
       

        merged_program = merge_nodes(self.graph)
        processed_program = postprocess(
            merged_program,
            qiskit_compat=self.qiskit_compat,
            literal_nodes=literal_nodes,
            literal_nodes_with_consumers=used_literal_nodes,
        )
        return leqo_dumps(processed_program)


class EnrichingProcessor(CommonProcessor):
    """
    Return enrichment for all nodes.
    """

    @staticmethod
    def from_compile_request(
        request: CompileRequest,
        enricher: Annotated[Enricher, Depends(get_enricher)],
    ) -> EnrichingProcessor:
        graph = FrontendGraph.create(request.nodes, request.edges)
        processor = EnrichingProcessor(enricher, graph, request.metadata)
        processor.target = request.compilation_target
        processor.original_request = request
        processor.qrms = request.qrms
        processor.service_deployment_models = request.serviceDeploymentModels
        return processor

    def _get_dummy_enrichment(
        self, node_id: str, requested_inputs: dict[int, LeqoSupportedType]
    ) -> ImplementationNode:
        return ImplementationNode(
            id=node_id,
            implementation=leqo_dumps(
                generate_pass_node_implementation(requested_inputs)
            ),
        )

    def _process_node(
        self,
        enriched_node: ImplementationNode,
        requested_inputs: dict[int, LeqoSupportedType],
    ) -> None:
        self.frontend_to_processed[enriched_node.id] = preprocess(
            ProgramNode(enriched_node.id),
            enriched_node.implementation,
            requested_inputs,
        )

    async def _enrich_inner_block(
        self, node: FrontendNode, block: NestedBlock
    ) -> AsyncIterator[ImplementationNode]:
        """
        Yield enrichments for nodes in inner block.
        """
        frontend_graph = FrontendGraph.create([*block.nodes, node], block.edges)
        for pred in list(frontend_graph.predecessors(node.id)):
            frontend_graph.remove_edge(pred, node.id)

        processor = EnrichingProcessor(self.enricher, frontend_graph, self.optimize)
        async for enriched_node in processor.enrich():
            if enriched_node.id != node.id:
                yield enriched_node

    async def enrich(
        self,
    ) -> AsyncIterator[ImplementationNode]:
        """
        Yield enrichment of nodes.
        """
        for node in topological_sort(self.frontend_graph):
            frontend_node = self.frontend_graph.node_data[node]
            requested_inputs, requested_values = self._resolve_inputs(node)

            match frontend_node:
                case RepeatNode():
                    border_node = self._get_dummy_enrichment(node, requested_inputs)
                    self._process_node(border_node, requested_inputs)
                    async for enriched_node in self._enrich_inner_block(
                        border_node, frontend_node.block
                    ):
                        yield enriched_node
                case IfThenElseNode():
                    border_node = self._get_dummy_enrichment(node, requested_inputs)
                    self._process_node(border_node, requested_inputs)
                    for block in (frontend_node.thenBlock, frontend_node.elseBlock):
                        async for enriched_node in self._enrich_inner_block(
                            border_node, block
                        ):
                            yield enriched_node
                case _:
                    enriched = await self.enricher.enrich(
                        frontend_node,
                        Constraints(
                            requested_inputs=requested_inputs,
                            optimizeWidth=self.optimize.optimizeWidth is not None,
                            optimizeDepth=self.optimize.optimizeDepth is not None,
                            requested_input_values=requested_values,
                        ),
                    )
                    enriched_node = (
                        enriched
                        if isinstance(enriched, ImplementationNode)
                        else ImplementationNode(
                            id=enriched.id,
                            label=enriched.label,
                            implementation=leqo_dumps(enriched.implementation),
                        )
                    )
                    self._process_node(enriched_node, requested_inputs)
                    yield enriched_node

    async def enrich_all(self) -> list[ImplementationNode]:
        """
        Get list of all enrichments.
        """
        return [x async for x in self.enrich()]


CLASSICAL_TYPES = {"int", "float", "angle", "boolean", "bit"}


class WorkflowProcessor(CommonProcessor):
    """Process a request to a workflow representation."""

    @staticmethod
    def from_compile_request(
        request: CompileRequest,
        enricher: Annotated[Enricher, Depends(get_enricher)],
    ) -> "WorkflowProcessor":
        graph = FrontendGraph.create(request.nodes, request.edges)
        processor = WorkflowProcessor(enricher, graph, request.metadata)
        processor.target = request.compilation_target
        processor.original_request = request
        processor.qrms = request.qrms
        processor.service_deployment_models = request.serviceDeploymentModels
        return processor

    async def process(self) -> str:
        """Run enrichment, classify nodes, group quantum nodes, and return BPMN XML."""
        enriching_processor = EnrichingProcessor(
            self.enricher,
            self.frontend_graph,
            self.optimize,
        )
        enriching_processor.target = "workflow"
        await enriching_processor.enrich_all()

        print("All nodes in the frontend graph:")
        for node_id in self.frontend_graph.nodes:
            node = self.frontend_graph.node_data[node_id]
            print(f"Node ID: {node.id}, Type: {getattr(node, 'type', None)}")

        # Identify quantum groups
        quantum_groups = await self.identify_quantum_groups()
        print(f"\nFound {len(quantum_groups)} quantum groups: {[g for g in quantum_groups.keys()]}")
        node_metadata = {}

        for node_id in self.frontend_graph.nodes:
            node_metadata[node_id] = {}

        # Attach metadata
        for group_id, nodes in quantum_groups.items():
            for node in nodes:
                node_id = getattr(node, "id", None)
                if node_id:
                    node_metadata[node_id]["quantum_group"] = group_id

        # Collapse quantum groups into single composite nodes
        nodes_dict = dict(self.frontend_graph.node_data)
        edges = list(self.frontend_graph.edges)

        # Build a mapping of quantum node ->group_id
        node_to_group = {}
        for gid, group_nodes in quantum_groups.items():
            for n in group_nodes:
                node_to_group[n.id] = gid

        # New node set after collapsing
        composite_nodes = {}
        for nid, node in nodes_dict.items():
            gid = node_to_group.get(nid)
            if gid:
                # Represent the entire group as one task node
                if gid not in composite_nodes:
                    composite_nodes[gid] = node  # pick first node as representative
            else:
                composite_nodes[nid] = node

        # Adjust edges: if both endpoints belong to same group ->remove; else remap to group IDs
        collapsed_edges = set()
        for src, tgt in edges:
            src_gid = node_to_group.get(src, src)
            tgt_gid = node_to_group.get(tgt, tgt)
            if src_gid != tgt_gid:
                collapsed_edges.add((src_gid, tgt_gid))
        collapsed_edges = list(collapsed_edges)

        # Generate BPMN
        bpmn_xml = _implementation_nodes_to_bpmn_xml("workflow_process", composite_nodes, collapsed_edges, metadata=node_metadata)
        return bpmn_xml



    async def identify_quantum_groups(self) -> dict[str, list[ImplementationNode]]:
        """
        Returns a dictionary of quantum groups keyed by group ID.
        """
        # Collect quantum nodes
        quantum_nodes = [
            self.frontend_graph.node_data[node_id]
            for node_id in self.frontend_graph.nodes
            if getattr(self.frontend_graph.node_data[node_id], "type", None) not in CLASSICAL_TYPES
        ]

        print(f"Quantum nodes: {[node.id for node in quantum_nodes]}")

        # Group by connected components using DFS
        groups = defaultdict(list)
        visited = set()

        def dfs(node: ImplementationNode, group_id: str):
            if node.id in visited:
                return
            visited.add(node.id)
            groups[group_id].append(node)

            # Traverse neighbors
            for neighbor_id in self.frontend_graph.successors(node.id):
                neighbor = self.frontend_graph.node_data[neighbor_id]
                if getattr(neighbor, "type", None) not in CLASSICAL_TYPES:
                    dfs(neighbor, group_id)
            for neighbor_id in self.frontend_graph.predecessors(node.id):
                neighbor = self.frontend_graph.node_data[neighbor_id]
                if getattr(neighbor, "type", None) not in CLASSICAL_TYPES:
                    dfs(neighbor, group_id)

        group_counter = 0
        for node in quantum_nodes:
            if node.id not in visited:
                dfs(node, f"quantum_group_{group_counter}")
                group_counter += 1

        return dict(groups)


class EnrichmentInserter:
    """
    Insert enrichment implementations for frontend-nodes into the Enricher.
    """

    inserts: list[SingleInsert]
    enricher: Enricher

    def __init__(
        self, inserts: list[SingleInsert], enricher: Enricher, engine: AsyncEngine
    ) -> None:
        self.inserts = inserts
        self.enricher = enricher
        self.engine = engine

    @staticmethod
    def from_insert_request(
        request: InsertRequest,
        enricher: Annotated[Enricher, Depends(get_enricher)],
        engine: Annotated[AsyncEngine, Depends(get_db_engine)],
    ) -> EnrichmentInserter:
        return EnrichmentInserter(request.inserts, enricher, engine)

    async def insert_all(self) -> None:
        """
        Insert all enrichments.
        """
        async with AsyncSession(self.engine) as session:
            for insert in self.inserts:
                processed = preprocess(ProgramNode(name="dummy"), insert.implementation)
                requested_inputs = {k: v.type for k, v in processed.io.inputs.items()}
                actual_width = processed.qubit.get_width()

                if (
                    insert.metadata.width is not None
                    and actual_width != insert.metadata.width
                ):
                    msg = f"Specified width does not match parsed width: {insert.metadata.width} != {actual_width}"
                    raise PreprocessingException(msg, insert.node)
                insert.metadata.width = actual_width

                await self.enricher.insert_enrichment(
                    insert.node,
                    insert.implementation,
                    requested_inputs,
                    insert.metadata,
                    session,
                )
            await session.commit()


def random_id(prefix="Flow"):
    return f"{prefix}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=7))}"

# BPMN namespaces
BPMN2_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
DC_NS = "http://www.omg.org/spec/DD/20100524/DC"
DI_NS = "http://www.omg.org/spec/DD/20100524/DI"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
CAMUNDA_NS="http://camunda.org/schema/1.0/bpmn" 
OpenTOSCA_NS="https://github.com/UST-QuAntiL/OpenTOSCA"

ET.register_namespace("bpmn2", BPMN2_NS)
ET.register_namespace("bpmndi", BPMNDI_NS)
ET.register_namespace("dc", DC_NS)
ET.register_namespace("di", DI_NS)
ET.register_namespace("xsi", XSI_NS)
ET.register_namespace("opentosca", OpenTOSCA_NS)
ET.register_namespace("camunda", CAMUNDA_NS)

def _implementation_nodes_to_bpmn_xml(process_id: str, nodes: dict, edges: list, metadata: dict = None) -> str:
    """Generate BPMN XML workflow diagram with correct left-to-right layout based on dependencies."""
    import xml.etree.ElementTree as ET
    import uuid
    from collections import deque, defaultdict

    metadata = metadata or {}

    def qn(ns, tag):
        return f"{{{ns}}}{tag}"

    # Root BPMN structure
    defs = ET.Element(
        qn(BPMN2_NS, "definitions"),
        {
            "id": "sample-diagram",
            "targetNamespace": "http://bpmn.io/schema/bpmn",
            qn(XSI_NS, "schemaLocation"): "http://www.omg.org/spec/BPMN/20100524/MODEL BPMN20.xsd",
        },
    )

    process = ET.SubElement(
        defs,
        qn(BPMN2_NS, "process"),
        {"id": f"Process_{process_id}", "isExecutable": "true"},
    )

    # Layout constants
    start_x, start_y = 252, 222
    task_w, task_h = 120, 80
    gap_x = 220
    gap_y = 150

    # Start and End Events
    start_id = "StartEvent_1"
    end_id = "EndEvent_1"
    start_event = ET.SubElement(process, qn(BPMN2_NS, "startEvent"), {"id": start_id})
    end_event = ET.SubElement(process, qn(BPMN2_NS, "endEvent"), {"id": end_id})

    # Build graph maps
    incoming = defaultdict(list)
    outgoing = defaultdict(list)
    for src, tgt in edges:
        outgoing[src].append(tgt)
        incoming[tgt].append(src)

    node_ids = list(nodes.keys())
    start_nodes = [nid for nid in node_ids if not incoming[nid]]
    end_nodes = [nid for nid in node_ids if not outgoing[nid]]

    # Topological order
    indegree = {nid: len(incoming[nid]) for nid in node_ids}
    queue = deque(start_nodes)
    topo_order = []

    while queue:
        nid = queue.popleft()
        topo_order.append(nid)
        for tgt in outgoing[nid]:
            indegree[tgt] -= 1
            if indegree[tgt] == 0:
                queue.append(tgt)

    # Fallback: include any isolated nodes
    for nid in node_ids:
        if nid not in topo_order:
            topo_order.append(nid)

    # Layout positions based on topological order
    task_positions = {}
    level_positions = defaultdict(list)
    node_level = {}

    for nid in start_nodes:
        node_level[nid] = 0

    # compute level (depth)
    for nid in topo_order:
        if nid not in node_level:
            preds = incoming[nid]
            if preds:
                node_level[nid] = max(node_level[p] for p in preds) + 1
            else:
                node_level[nid] = 0
        level_positions[node_level[nid]].append(nid)

    # Assign x/y positions
    for level, nids in level_positions.items():
        for i, nid in enumerate(nids):
            x = start_x + 170 + level * (task_w + gap_x)
            y = 200 + i * (task_h + gap_y)
            task_positions[nid] = (x, y)
    end_x = start_x + 170 + (max(node_level.values(), default=0) + 1) * (task_w + gap_x)

    # Service Tasks
    for nid, node in nodes.items():
        task_id = f"Task_{nid}"
        node_type = getattr(node, "type", "Task")
        node_meta = metadata.get(nid, {})

        task_name = node_type or "Task"
        if "quantum_group" in node_meta:
            task_name += f" (Quantum Group {node_meta['quantum_group']})"

        task_el = ET.SubElement(
            process,
            qn(BPMN2_NS, "serviceTask"),
            {"id": task_id, "name": task_name},
        )

        # Add metadata as BPMN extension elements
        if node_meta:
            ext = ET.SubElement(task_el, qn(BPMN2_NS, "extensionElements"))
            for key, val in node_meta.items():
                ET.SubElement(ext, qn(BPMN2_NS, "property"), {"name": key, "value": str(val)})

    # Sequence Flows
    flow_map = []

    # Start -> nodes with no incoming edges
    for start_node in start_nodes:
        flow_id = f"Flow_{uuid.uuid4().hex[:7]}"
        flow_map.append((flow_id, start_id, start_node))
        ET.SubElement(start_event, qn(BPMN2_NS, "outgoing")).text = flow_id

    # Normal edges
    for src, tgt in edges:
        flow_id = f"Flow_{uuid.uuid4().hex[:7]}"
        flow_map.append((flow_id, src, tgt))

    # Nodes with no outgoing edges -> End
    for end_node in end_nodes:
        flow_id = f"Flow_{uuid.uuid4().hex[:7]}"
        flow_map.append((flow_id, end_node, end_id))
        ET.SubElement(end_event, qn(BPMN2_NS, "incoming")).text = flow_id

    # Add incoming/outgoing tags for all
    for fid, src, tgt in flow_map:
        src_task = process.find(f".//*[@id='Task_{src}']")
        tgt_task = process.find(f".//*[@id='Task_{tgt}']")
        if src_task is not None:
            ET.SubElement(src_task, qn(BPMN2_NS, "outgoing")).text = fid
        if tgt_task is not None:
            ET.SubElement(tgt_task, qn(BPMN2_NS, "incoming")).text = fid

        ET.SubElement(
            process,
            qn(BPMN2_NS, "sequenceFlow"),
            {
                "id": fid,
                "sourceRef": f"{'Task_' + src if src not in (start_id, end_id) else src}",
                "targetRef": f"{'Task_' + tgt if tgt not in (start_id, end_id) else tgt}",
            },
        )

    # Diagram
    diagram = ET.SubElement(defs, qn(BPMNDI_NS, "BPMNDiagram"), {"id": "BPMNDiagram_1"})
    plane = ET.SubElement(
        diagram,
        qn(BPMNDI_NS, "BPMNPlane"),
        {"id": "BPMNPlane_1", "bpmnElement": f"Process_{process_id}"},
    )

    # Start shape
    start_shape = ET.SubElement(plane, qn(BPMNDI_NS, "BPMNShape"),
        {"id": f"{start_id}_di", "bpmnElement": start_id})
    ET.SubElement(start_shape, qn(DC_NS, "Bounds"), x=str(start_x), y=str(start_y), width="36", height="36")

    # Task shapes
    for nid, (x, y) in task_positions.items():
        shape = ET.SubElement(plane, qn(BPMNDI_NS, "BPMNShape"),
            {"id": f"Task_{nid}_di", "bpmnElement": f"Task_{nid}"})
        ET.SubElement(shape, qn(DC_NS, "Bounds"), x=str(x), y=str(y), width=str(task_w), height=str(task_h))

    # End shape
    end_shape = ET.SubElement(plane, qn(BPMNDI_NS, "BPMNShape"),
        {"id": f"{end_id}_di", "bpmnElement": end_id})
    ET.SubElement(end_shape, qn(DC_NS, "Bounds"), x=str(end_x), y=str(start_y), width="36", height="36")

    # Edges
    for fid, src, tgt in flow_map:
        edge = ET.SubElement(plane, qn(BPMNDI_NS, "BPMNEdge"), {"id": f"{fid}_di", "bpmnElement": fid})

        if src == start_id:
            sx, sy = start_x + 36, start_y + 18
        else:
            sx, sy = task_positions[src]
            sx += task_w
            sy += 40

        if tgt == end_id:
            tx, ty = end_x, start_y + 18
        else:
            tx, ty = task_positions[tgt]
            ty += 40

        ET.SubElement(edge, qn(DI_NS, "waypoint"), x=str(sx), y=str(sy))
        ET.SubElement(edge, qn(DI_NS, "waypoint"), x=str(tx), y=str(ty))

    return ET.tostring(defs, encoding="utf-8", xml_declaration=True).decode("utf-8")

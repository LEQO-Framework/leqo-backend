"""
Provides the ore logic of the backend.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import AsyncIterator
import re
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
from app.transformation_manager.frontend_graph import FrontendGraph, TBaseNode
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
import io
import zipfile
from pathlib import Path
import os
import io
import json

# BPMN Layout Configuration
BPMN_START_X = 252              # X position of start event
BPMN_START_Y = 222              # Y position of start event
BPMN_TASK_WIDTH = 120           # Width of each task box
BPMN_TASK_HEIGHT = 80           # Height of each task box
BPMN_GAP_X = 220                # Horizontal spacing between tasks
BPMN_GAP_Y = 150                # Vertical spacing between rows
BPMN_CHAIN_X_OFFSET = 170       # Offset from start to first chain task
BPMN_CHAIN_Y_BASE = 200         # Base Y position for chain tasks
BPMN_WAYPOINT_Y_OFFSET = 40     # Y offset to task center for waypoints
BPMN_HUMAN_Y_BASE = 200         # Base Y position for human task
BPMN_END_EVENT_WIDTH = 36       # Width of start/end events
BPMN_END_EVENT_HEIGHT = 36      # Height of start/end events
BPMN_FLOW_ID_LENGTH = 7         # Length of generated flow IDs
BPMN_GW_WIDTH = 50              # Width of gateway
BPMN_GW_HEIGHT = 50             # Height of gateway



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
        original_request: CompileRequest |None = None,
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
        self.original_request = original_request

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
        processor = WorkflowProcessor(enricher, graph, request.metadata, original_request=request)
        processor.target = request.compilation_target
        processor.original_request = request
        return processor
        
    async def process(self) -> tuple[str, bytes]:
        """Run enrichment, classify nodes, group quantum nodes, and return BPMN XML."""

        # Identify quantum groups
        quantum_groups = await self.identify_quantum_groups()

        # Prepare node metadata
        node_metadata: dict[str, dict[str, Any]] = {node_id: {} for node_id in self.frontend_graph.nodes}

        # Attach quantum group info
        for group_id, nodes in quantum_groups.items():
            for node in nodes:
                node_id = getattr(node, "id", None)
                if node_id:
                    node_metadata[node_id]["quantum_group"] = group_id

        # Collapse quantum groups into composite nodes
        nodes_dict: dict[str, Any] = dict(self.frontend_graph.node_data)
        edges = list(self.frontend_graph.edges)

        node_to_group: dict[str, str] = {}
        for gid, group_nodes in quantum_groups.items():
            for n in group_nodes:
                node_to_group[n.id] = gid

        composite_nodes: dict[str, Any] = {}
        for nid, node in nodes_dict.items():
            ngid = node_to_group.get(nid)
            if ngid:
                if gid not in composite_nodes:
                    composite_nodes[ngid] = node  # pick representative
            elif getattr(node, "type", None) not in CLASSICAL_TYPES:
                composite_nodes[nid] = node

        # Remap edges to composite nodes
        collapsed_edges: set[tuple[str, str]] = set()
        for src, tgt in edges:
            src_gid = node_to_group.get(src, src)
            tgt_gid = node_to_group.get(tgt, tgt)
            if src_gid != tgt_gid and src_gid in composite_nodes and tgt_gid in composite_nodes:
                collapsed_edges.add((src_gid, tgt_gid))
        collapsed_edges_list: list[tuple[str,str]] = list(collapsed_edges)

        # Generate BPMN XML
        bpmn_xml, all_activities = _implementation_nodes_to_bpmn_xml(
            "workflow_process",
            composite_nodes,
            collapsed_edges_list,
            metadata=node_metadata,
            start_event_classical_nodes=[node for node in nodes_dict.values() if getattr(node, "type", None) in CLASSICAL_TYPES],
            containsPlaceholder=self.original_request.metadata.containsPlaceholder        
        )
        print("Service Task Generation")
        # Generate ZIP-of-ZIPs for Python files
        #service_zip_bytes = await self.generate_service_zips(all_activities, node_metadata)
        
        # Generate QRMs
        qrms = await generate_qrms(quantum_groups)
        #return service_zip_bytes
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

        # print(f"Quantum nodes: {[node.id for node in quantum_nodes]}")

        # Group by connected components using DFS
        groups: dict[str, list[Any]] = defaultdict(list)
        visited = set()

        def dfs(node: TBaseNode, group_id: str) -> None:
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

    async def generate_service_zips(self,composite_nodes: list[str],node_metadata: dict[str, dict[str, Any]]) -> bytes:
        """
        Generate one ZIP per node.
        Each ZIP contains a single service with logic ONLY for that node.
        """
        output_dir = "/tmp/generated_services"
        os.makedirs(output_dir, exist_ok=True)

        master_zip_buffer = io.BytesIO()

        with zipfile.ZipFile(
            master_zip_buffer,
            mode="w",
            compression=zipfile.ZIP_DEFLATED
        ) as master_zip:

            for node_id in composite_nodes:
                activity_name = "Activity_" + node_id.replace(" ", "_")

                if "_human" in activity_name:
                    continue

                activity_zip_buffer = io.BytesIO()

                with zipfile.ZipFile(
                    activity_zip_buffer,
                    mode="w",
                    compression=zipfile.ZIP_DEFLATED
                ) as activity_zip:

                    # ---------- inner service.zip ----------
                    inner_service_buffer = io.BytesIO()
                    with zipfile.ZipFile(
                        inner_service_buffer,
                        mode="w",
                        compression=zipfile.ZIP_DEFLATED
                    ) as inner_service_zip:

                        # ---------- serialize request ----------
                        assert self.original_request is not None
                        try:
                            full_request_json = self.original_request.json()
                        except Exception:
                            full_request_json = json.loads(
                                self.original_request.json(
                                    exclude_none=True,
                                    exclude_unset=True
                                )
                            )

                        safe_request_str = json.dumps(
                            full_request_json,
                            indent=4,
                            ensure_ascii=False
                        )

                        # ---------- app.py ----------
                        app_lines = [
                            "import requests",
                            "import time",
                            "import json",
                            "import os",
                            "",
                            "BACKEND_URL = os.environ.get('BACKEND_URL', 'http://localhost:8000')",
                            "",
                            "def main(**kwargs):",
                        ]

                        # ===== NODE-SPECIFIC LOGIC =====

                        if node_id.endswith("_model"):
                            app_lines += [
                                f"    # Logic for {node_id}",
                                f"    model_data = {safe_request_str}",
                                f"    return model_data",
                            ]

                        elif node_id.endswith("_send_compile"):
                            app_lines += [
                                f"    # Logic for {node_id}",
                                f"    model_data = {safe_request_str}",
                                f"    model = json.loads(model_data)",
                                f"    url = f\"{{BACKEND_URL}}/compile\"",
                                f"    response = requests.post(url, json=model)",
                                f"    response.raise_for_status()",
                                f"    data = response.json()",
                                f"    uuid = data.get('uuid')",
                                f"    if not uuid:",
                                f"        raise ValueError('Backend response does not contain uuid')",
                                f"    return uuid"
                            ]

                        elif node_id.endswith("_poll_result"):
                            app_lines += [
                                f"    # Logic for {node_id}",
                                f"    uuid = kwargs.get('uuid')",
                                f"    if not uuid:",
                                f"        raise ValueError('Missing uuid')",
                                f"    status_url = f\"{{BACKEND_URL}}/status/{{uuid}}\"",
                                f"    for attempt in range(20):",
                                f"        resp = requests.get(status_url)",
                                f"        if resp.ok:",
                                f"            data = resp.json()",
                                f"            if data.get('status') in ('completed','failed'):",
                                f"                return data",
                                f"        time.sleep(10)",
                                f"    return {{'status': 'timeout'}}",
                            ]

                        elif node_id.endswith("_set_vars"):
                            app_lines += [
                                f"    # Logic for {node_id}",
                                f"    status = kwargs.get('status')",
                                f"    location = kwargs.get('location')",
                                f"    result = {{'status': status, 'location': location}}",
                                f"    with open('final_result.json', 'w') as f:",
                                f"        json.dump(result, f)",
                                f"    return result",
                            ]

                        else:
                            app_lines += [
                                f"    raise NotImplementedError('Unknown node type: {node_id}')"
                            ]

                        inner_service_zip.writestr(
                            "app.py",
                            "\n".join(app_lines)
                        )

                        # ---------- polling_agent.py ----------
                        polling_agent_code = (
                            "import threading\n"
                            "import base64\n"
                            "import os\n"
                            "import requests\n"
                            "import app\n\n"
                            "def poll():\n"
                            "    body = {\n"
                            "        'workerId': 'WP67GZ6N9ZX5',\n"
                            "        'maxTasks': 1,\n"
                            "        'topics': [{'topicName': topic, 'lockDuration': 60000}]\n"
                            "    }\n"
                            "    try:\n"
                            "        response = requests.post(pollingEndpoint + '/fetchAndLock', json=body)\n"
                            "        if response.status_code == 200:\n"
                            "            for task in response.json():\n"
                            "                variables = task.get('variables', {})\n"
                            "                result = app.main()\n"
                            "                body = {'workerId': 'WP67GZ6N9ZX5', 'variables': {}}\n"
                            "                body['variables']['result'] = {\n"
                            "                    'value': base64.b64encode(str(result).encode()).decode(),\n"
                            "                    'type': 'File',\n"
                            "                    'valueInfo': {'filename': 'result.txt'}\n"
                            "                }\n"
                            "                requests.post(\n"
                            "                    pollingEndpoint + '/' + task.get('id') + '/complete',\n"
                            "                    json=body\n"
                            "                )\n"
                            "    except Exception as e:\n"
                            "        print('Polling error:', e)\n"
                            "    threading.Timer(8, poll).start()\n\n"
                            "camundaEndpoint = os.environ['CAMUNDA_ENDPOINT']\n"
                            "pollingEndpoint = camundaEndpoint + '/external-task'\n"
                            "topic = os.environ['CAMUNDA_TOPIC']\n"
                            "poll()\n"
                        )

                        inner_service_zip.writestr(
                            "polling_agent.py",
                            polling_agent_code
                        )

                        inner_service_zip.writestr(
                            "requirements.txt",
                            "requests\n"
                        )

                    # ---------- Docker layer ----------
                    middle_service_buffer = io.BytesIO()
                    with zipfile.ZipFile(
                        middle_service_buffer,
                        mode="w",
                        compression=zipfile.ZIP_DEFLATED
                    ) as middle_zip:

                        middle_zip.writestr(
                            "service.zip",
                            inner_service_buffer.getvalue()
                        )

                        middle_zip.writestr(
                            "Dockerfile",
                            """FROM python:3.8-slim
    COPY service.zip /tmp/service.zip
    RUN apt-get update && apt-get install -y unzip \
        && unzip /tmp/service.zip -d /service \
        && pip install -r /service/requirements.txt
    CMD ["python", "/service/polling_agent.py"]
    """
                        )

                    activity_zip.writestr(
                        "service.zip",
                        middle_service_buffer.getvalue()
                    )

                master_zip.writestr(
                    f"{activity_name}.zip",
                    activity_zip_buffer.getvalue()
                )

        return master_zip_buffer.getvalue()





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


def random_id(prefix: str ="Flow") -> str:
    return f"{prefix}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=7))}"

# BPMN namespaces
BPMN2_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
DC_NS = "http://www.omg.org/spec/DD/20100524/DC"
DI_NS = "http://www.omg.org/spec/DD/20100524/DI"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
CAMUNDA_NS="http://camunda.org/schema/1.0/bpmn" 
OpenTOSCA_NS="https://github.com/UST-QuAntiL/OpenTOSCA"
QUANTME_NS="https://github.com/UST-QuAntiL/QuantME-Quantum4BPMN"

ET.register_namespace("bpmn2", BPMN2_NS)
ET.register_namespace("bpmndi", BPMNDI_NS)
ET.register_namespace("dc", DC_NS)
ET.register_namespace("di", DI_NS)
ET.register_namespace("xsi", XSI_NS)
ET.register_namespace("opentosca", OpenTOSCA_NS)
ET.register_namespace("camunda", CAMUNDA_NS)
ET.register_namespace("quantme", QUANTME_NS)

def _implementation_nodes_to_bpmn_xml(process_id: str, nodes: dict[str, Any], edges: list[tuple[str,str]], metadata: dict[str, dict[str, Any]] | None = None, start_event_classical_nodes: list[Any] | None = None, containsPlaceholder: bool = False) -> tuple[str, list[str]]:
    """Generate BPMN XML workflow diagram with correct left-to-right layout.

    This version inserts, immediately after the StartEvent, a chain of four
    service tasks:
        Model -> Send Compile Request -> Poll Result -> Set Variables

    For composite nodes which are quantum groups (ids starting with 'quantum_group_')
    the same chain is created per group and connected to the group's node.
    For each original start-node in the graph (no incoming edges) the last
    chain task (Set Variables) is linked into that node so the chain appears
    before the node in the diagram.
    """
    import xml.etree.ElementTree as ET
    import uuid
    from collections import defaultdict, deque
    
    metadata = metadata or {}
    start_event_classical_nodes = start_event_classical_nodes or []

    def qn(ns: str, tag: str) -> str:
        return f"{{{ns}}}{tag}"

    # Root definitions
    defs = ET.Element(
        qn(BPMN2_NS, "definitions"),
        {
            "id": "sample-diagram",
            "targetNamespace": "http://bpmn.io/schema/bpmn",
            qn(XSI_NS, "schemaLocation"): "http://www.omg.org/spec/BPMN/20100524/MODEL BPMN20.xsd",
        },
    )

    process = ET.SubElement(defs, qn(BPMN2_NS, "process"), {"id": f"Process_{process_id}", "isExecutable": "true"})

    start_id = "StartEvent_1"
    end_id = "EndEvent_1"
    start_event = ET.SubElement(process, qn(BPMN2_NS, "startEvent"), {"id": start_id})
    end_event = ET.SubElement(process, qn(BPMN2_NS, "endEvent"), {"id": end_id})

    # human task
    human_id = "Task_human"
    ET.SubElement(process, qn(BPMN2_NS, "userTask"), {"id": human_id, "name": "Analyze Results"})

    # Add classical nodes as start-event form fields
    if start_event_classical_nodes:
        ext = ET.SubElement(start_event, qn(BPMN2_NS, "extensionElements"))
        form_data = ET.SubElement(ext, qn(CAMUNDA_NS, "formData"))
        for node in start_event_classical_nodes:
            node_id = getattr(node, "id", None) or "unknown"
            node_label = getattr(node, "label", None) or node_id
            ET.SubElement(
                form_data,
                qn(CAMUNDA_NS, "formField"),
                {
                    "id": f"Input_{node_id.replace("-","_")}_value",
                    "label": node_label,
                    "type": "string",
                    "defaultValue": "0"
                }
            )

    # Build incoming/outgoing maps from collapsed edges
    incoming, outgoing = defaultdict(list), defaultdict(list)
    for src, tgt in edges:
        outgoing[src].append(tgt)
        incoming[tgt].append(src)

    node_ids = list(nodes.keys())
    start_nodes = [nid for nid in node_ids if not incoming[nid]]
    end_nodes = [nid for nid in node_ids if not outgoing[nid]]

    # check if parallel gateways are needed
    use_parallel = len(start_nodes) > 1
    # parallel gateways
    fork_id = "Gateway_parallel_fork"
    join_id = "Gateway_parallel_join"
    if use_parallel:
        ET.SubElement(process, qn(BPMN2_NS, "parallelGateway"), {"id": fork_id})
        ET.SubElement(process, qn(BPMN2_NS, "parallelGateway"), {"id": join_id})

    # Topological sort
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
    for nid in node_ids:
        if nid not in topo_order:
            topo_order.append(nid)

    inserted_chains = {}  # start_node -> (model_id, send_id, poll_id, setvars_id)

    # For each start_node create a dedicated chain (if it's a quantum_group, chain is per-group)
    for start_node in start_nodes:
        # chain element ids (unique)
        model_id = f"Task_{start_node}_model"
        send_id = f"Task_{start_node}_send_compile"
        poll_id = f"Task_{start_node}_poll_result"
        setvars_id = f"Task_{start_node}_set_vars"
        inserted_chains[start_node] = (model_id, send_id, poll_id, setvars_id)

    # Determine node levels first (base)
    task_positions = {}
    level_positions = defaultdict(list)
    node_level = {}

    # fork-gateway right from start_id
    if use_parallel:
        fork_x = BPMN_START_X + 80
        fork_y = BPMN_START_Y - (BPMN_GW_HEIGHT - BPMN_END_EVENT_HEIGHT) // 2
        task_positions[fork_id] = (fork_x, fork_y)

    # start chains will be at level 0, original nodes pushed to level+1
    for nid in node_ids:
        if nid in start_nodes:
            node_level[nid] = 1  # will be after inserted chain
        # other nodes left to compute

    # compute levels by topo_order, using incoming preds' levels
    for nid in topo_order:
        if nid not in node_level:
            preds = incoming[nid]
            if preds:
                node_level[nid] = max(node_level.get(p, 0) for p in preds) + 1
            else:
                node_level[nid] = 1  # if isolated, place after chain level
        level_positions[node_level[nid]].append(nid)

    # place chain tasks at level 0; if multiple start nodes, they'll be stacked vertically
    chain_level = 0
    for i, start_node in enumerate(start_nodes):
        # one row per start_node chain, stacked by i
        x = BPMN_START_X + BPMN_CHAIN_X_OFFSET + chain_level * (BPMN_TASK_WIDTH + BPMN_GAP_X)
        y = BPMN_CHAIN_Y_BASE + i * (BPMN_TASK_HEIGHT + BPMN_GAP_Y)
        model_id, send_id, poll_id, setvars_id = inserted_chains[start_node]
        if containsPlaceholder:
            task_positions[model_id] = (x, y)
            task_positions[send_id] = (x + (BPMN_TASK_WIDTH + BPMN_GAP_X), y)
            task_positions[poll_id] = (x + 2 * (BPMN_TASK_WIDTH + BPMN_GAP_X), y)
            task_positions[setvars_id] = (x + 3 * (BPMN_TASK_WIDTH + BPMN_GAP_X), y)
   
    # assign positions for original nodes from level_positions
    for level, nids in level_positions.items():
        for i, nid in enumerate(nids):
            # shift x by +1 level because chain occupies level 0
            x = BPMN_START_X + BPMN_CHAIN_X_OFFSET + (level + 3) * (BPMN_TASK_WIDTH + BPMN_GAP_X)
            y = BPMN_CHAIN_Y_BASE + i * (BPMN_TASK_HEIGHT + BPMN_GAP_Y)
            task_positions[nid] = (x, y)
            
    # Human task position: left from end_id
    if task_positions:
        max_x = max(x for x, _ in task_positions.values())
    else:
        # if there are no tasks
        max_x = BPMN_START_X + BPMN_CHAIN_X_OFFSET

    human_y = BPMN_CHAIN_Y_BASE
    for end_node in end_nodes:
        end_key = f"Task_{end_node}" if f"Task_{end_node}" in task_positions else end_node
        if end_key in task_positions:
            _, human_y = task_positions[end_key]
            break

    human_x = max_x + BPMN_TASK_WIDTH + BPMN_GAP_X
    task_positions[human_id] = (human_x, human_y)

    # join-gateway left from human task
    if use_parallel:
        join_x = human_x - (BPMN_GW_WIDTH + BPMN_GAP_X // 2)
        join_y = human_y + (BPMN_TASK_HEIGHT - BPMN_GW_HEIGHT) // 2
        task_positions[join_id] = (join_x, join_y)

    # end_id right from human task
    end_x = human_x + BPMN_TASK_WIDTH + BPMN_GAP_X

    # Create service tasks for all original composite nodes
    for nid, node in nodes.items():
        # if we already created chain tasks for this nid (they're not in `nodes`), skip
        # nodes are only composite nodes, chain tasks are additional synthetic tasks
        task_id = f"Task_{nid}"
        node_type = getattr(node, "type", "Task")
        if node_type == "encode":
            task_el = ET.SubElement(process, qn(QUANTME_NS, "dataPreparationTask"), {"id": task_id, "name": node_type})
        elif node_type == "measurement":
            task_el = ET.SubElement(process, qn(QUANTME_NS, "quantumCircuitExecutionTask"), {"id": task_id, "name": node_type})
        elif node_type == "prepare":
            task_el = ET.SubElement(process, qn(QUANTME_NS, "quantumCircuitLoadingTask"), {"id": task_id, "name": node_type})
        elif node_type == "group":
            task_el = ET.SubElement(process, qn(QUANTME_NS, "quantumComputationTask"), {"id": task_id, "name": node_type})
        else:
            task_el = ET.SubElement(process, qn(BPMN2_NS, "serviceTask"), {"id": task_id, "name": node_type, "opentosca:deploymentModelUrl": f"{{{{ wineryEndpoint }}}}/servicetemplates/http%253A%252F%252Fquantil.org%252Fquantme%252Fpull/{nid}/?csar"})

        # Add metadata as extensionElements/properties
        for key, val in metadata.get(nid, {}).items():
            ext = ET.SubElement(task_el, qn(BPMN2_NS, "extensionElements"))
            ET.SubElement(ext, qn(BPMN2_NS, "property"), {"name": key, "value": str(val)})

    if containsPlaceholder:
        # Create synthetic service tasks for chains (Model, Send Compile, Poll Result, Set Variables)
        # One chain per start_node
        for start_node, (model_id, send_id, poll_id, setvars_id) in inserted_chains.items():
            # model
            ET.SubElement(process, qn(BPMN2_NS, "serviceTask"), {"id": model_id, "name": "Set Model", "opentosca:deploymentModelUrl": f"{{{{ wineryEndpoint }}}}/servicetemplates/http%253A%252F%252Fquantil.org%252Fquantme%252Fpull/Activity_{model_id}/?csar"})
            # send compile request
            ET.SubElement(process, qn(BPMN2_NS, "serviceTask"), {"id": send_id, "name": "Send Compile Request", "opentosca:deploymentModelUrl": f"{{{{ wineryEndpoint }}}}/servicetemplates/http%253A%252F%252Fquantil.org%252Fquantme%252Fpull/Activity_{send_id}/?csar"})
            # poll result
            ET.SubElement(process, qn(BPMN2_NS, "serviceTask"), {"id": poll_id, "name": "Poll Result", "opentosca:deploymentModelUrl": f"{{{{ wineryEndpoint }}}}/servicetemplates/http%253A%252F%252Fquantil.org%252Fquantme%252Fpull/Activity_{poll_id}/?csar"})
            # set variables
            ET.SubElement(process, qn(BPMN2_NS, "serviceTask"), {"id": setvars_id, "name": "Set Variables", "opentosca:deploymentModelUrl": f"{{{{ wineryEndpoint }}}}/servicetemplates/http%253A%252F%252Fquantil.org%252Fquantme%252Fpull/Activity_{setvars_id}/?csar"})

    # Sequence flows (we will build flow_map with tuples (flow_id, src, tgt))
    flow_map = []

    if use_parallel:
        # Start -> fork
        f_start_fork = f"Flow_{uuid.uuid4().hex[:BPMN_FLOW_ID_LENGTH]}"
        flow_map.append((f_start_fork, start_id, fork_id))

        # fork -> each model task (one per start_node)
        for start_node in start_nodes:
            model_id, send_id, poll_id, setvars_id = inserted_chains[start_node]
            if containsPlaceholder:
                # Fork -> Model
                f1 = f"Flow_{uuid.uuid4().hex[:BPMN_FLOW_ID_LENGTH]}"
                flow_map.append((f1, fork_id, model_id))
                # Model -> Send
                f2 = f"Flow_{uuid.uuid4().hex[:BPMN_FLOW_ID_LENGTH]}"
                flow_map.append((f2, model_id, send_id))
                # Send -> Poll
                f3 = f"Flow_{uuid.uuid4().hex[:BPMN_FLOW_ID_LENGTH]}"
                flow_map.append((f3, send_id, poll_id))
                # Poll -> SetVars
                f4 = f"Flow_{uuid.uuid4().hex[:BPMN_FLOW_ID_LENGTH]}"
                flow_map.append((f4, poll_id, setvars_id))
                # SetVars -> original start node
                f5 = f"Flow_{uuid.uuid4().hex[:BPMN_FLOW_ID_LENGTH]}"
                flow_map.append((f5, setvars_id, start_node))
            else: 
                f6 = f"Flow_{uuid.uuid4().hex[:BPMN_FLOW_ID_LENGTH]}"
                flow_map.append((f6, fork_id, start_node))
   
    else:
        # Start -> each model task (one per start_node)
        only_start = start_nodes[0]
        model_id, send_id, poll_id, setvars_id = inserted_chains[only_start]
        if containsPlaceholder:
            # Flow Start -> Model
            f1 = f"Flow_{uuid.uuid4().hex[:BPMN_FLOW_ID_LENGTH]}"
            flow_map.append((f1, start_id, model_id))
            # Model -> Send
            f2 = f"Flow_{uuid.uuid4().hex[:BPMN_FLOW_ID_LENGTH]}"
            flow_map.append((f2, model_id, send_id))
            # Send -> Poll
            f3 = f"Flow_{uuid.uuid4().hex[:BPMN_FLOW_ID_LENGTH]}"
            flow_map.append((f3, send_id, poll_id))
            # Poll -> SetVars
            f4 = f"Flow_{uuid.uuid4().hex[:BPMN_FLOW_ID_LENGTH]}"
            flow_map.append((f4, poll_id, setvars_id))
            # SetVars -> original start node
            f5 = f"Flow_{uuid.uuid4().hex[:BPMN_FLOW_ID_LENGTH]}"
            flow_map.append((f5, setvars_id, start_node))
        else: 
            f6 = f"Flow_{uuid.uuid4().hex[:BPMN_FLOW_ID_LENGTH]}"
            flow_map.append((f6, start_id, start_node))

    # Add original collapsed edges (connect tasks/nodes as before)
    for src, tgt in edges:
        # If src or tgt are chains (shouldn't be), they are left as-is. Otherwise these map to Task_{id}
        f = f"Flow_{uuid.uuid4().hex[:BPMN_FLOW_ID_LENGTH]}"
        flow_map.append((f, src, tgt))

    # Last: nodes with no outgoing go to a the parallel gateway or human task
    # Note: ensure we attach flows from actual last tasks (those Task_{nid}) to end
    if use_parallel:
        # end_node -> join
        for end_node in end_nodes:
            f = f"Flow_{uuid.uuid4().hex[:BPMN_FLOW_ID_LENGTH]}"
            flow_map.append((f, end_node, join_id))

        # join -> human_id
        f_join_human = f"Flow_{uuid.uuid4().hex[:BPMN_FLOW_ID_LENGTH]}"
        flow_map.append((f_join_human, join_id, human_id))

    else:
        # end_node -> human_id
        for end_node in end_nodes:
            f = f"Flow_{uuid.uuid4().hex[:BPMN_FLOW_ID_LENGTH]}"
            flow_map.append((f, end_node, human_id))

    # human_id -> end_id
    f = f"Flow_{uuid.uuid4().hex[:BPMN_FLOW_ID_LENGTH]}"
    flow_map.append((f, human_id, end_id))

    # Add incoming/outgoing and sequenceFlow elements for all flows in flow_map
    for fid, src, tgt in flow_map:
        # src/ tgt can be StartEvent_1, EndEvent_1, synthetic Task_{...} or real Task_{nid}
        # Ensure we add outgoing to the source element if present
        # The process.find search needs the exact id used in element creation above
        # Special-case start_id and end_id
        # If src is one of our synthetic chain task ids, it's present as id directly
        # If src is a composite node id, the element id is Task_{src}
        def is_direct_id(x: str) -> bool:
            direct = (start_id, end_id, human_id)
            if use_parallel:
                direct = direct + (fork_id, join_id)
            return x in direct or x.startswith(("Task_", "Gateway_"))


        src_search_id = src if is_direct_id(src) else f"Task_{src}"
        tgt_search_id = tgt if is_direct_id(tgt) else f"Task_{tgt}"

        src_el = process.find(f".//*[@id='{src_search_id}']")
        tgt_el = process.find(f".//*[@id='{tgt_search_id}']")

        if src_el is not None:
            ET.SubElement(src_el, qn(BPMN2_NS, "outgoing")).text = fid
        if tgt_el is not None:
            ET.SubElement(tgt_el, qn(BPMN2_NS, "incoming")).text = fid

        ET.SubElement(process, qn(BPMN2_NS, "sequenceFlow"), {
            "id": fid,
            "sourceRef": src_search_id,
            "targetRef": tgt_search_id
        })

    # Diagram shapes and edges
    diagram = ET.SubElement(defs, qn(BPMNDI_NS, "BPMNDiagram"), {"id": "BPMNDiagram_1"})
    plane = ET.SubElement(diagram, qn(BPMNDI_NS, "BPMNPlane"), {"id": "BPMNPlane_1", "bpmnElement": f"Process_{process_id}"})

    # Start shape
    start_shape = ET.SubElement(plane, qn(BPMNDI_NS, "BPMNShape"), {"id": f"{start_id}_di", "bpmnElement": start_id})
    ET.SubElement(start_shape, qn(DC_NS, "Bounds"), x=str(BPMN_START_X), y=str(BPMN_START_Y), width=str(BPMN_END_EVENT_WIDTH), height=str(BPMN_END_EVENT_HEIGHT))

    # Task shapes - include synthetic chain tasks and real tasks
    for nid, (x, y) in task_positions.items():
        if nid.startswith(("Task_", "Gateway_")):
            shape_id = nid
        else:
            shape_id = f"Task_{nid}"

        shape = ET.SubElement(
            plane, qn(BPMNDI_NS, "BPMNShape"),
            {"id": f"{shape_id}_di", "bpmnElement": shape_id}
        )

        if shape_id.startswith("Gateway_"):
            w, h = BPMN_GW_WIDTH, BPMN_GW_HEIGHT
        else:
            w, h = BPMN_TASK_WIDTH, BPMN_TASK_HEIGHT

        ET.SubElement(shape, qn(DC_NS, "Bounds"), x=str(x), y=str(y), width=str(w), height=str(h))


    # End shape
    end_shape = ET.SubElement(plane, qn(BPMNDI_NS, "BPMNShape"), {"id": f"{end_id}_di", "bpmnElement": end_id})
    ET.SubElement(end_shape, qn(DC_NS, "Bounds"), x=str(end_x), y=str(BPMN_START_Y), width=str(BPMN_END_EVENT_WIDTH), height=str(BPMN_END_EVENT_HEIGHT))

    # Edge shapes: create waypoints for every flow in flow_map
    def get_pos_and_size(node_id: str):
        key = node_id if node_id.startswith(("Task_", "Gateway_")) else f"Task_{node_id}"
        x, y = task_positions.get(key, task_positions.get(node_id, (BPMN_START_X, BPMN_START_Y)))
        if key.startswith("Gateway_"):
            return x, y, BPMN_GW_WIDTH, BPMN_GW_HEIGHT
        return x, y, BPMN_TASK_WIDTH, BPMN_TASK_HEIGHT

    for fid, src, tgt in flow_map:
        edge = ET.SubElement(
            plane, qn(BPMNDI_NS, "BPMNEdge"),
            {"id": f"{fid}_di", "bpmnElement": fid}
        )

        # Source waypoint
        if src == start_id:
            sx, sy = BPMN_START_X + BPMN_END_EVENT_WIDTH, BPMN_START_Y + BPMN_END_EVENT_HEIGHT // 2
        else:
            x, y, w, h = get_pos_and_size(src)
            sx, sy = x + w, y + h // 2

        # Target waypoint
        if tgt == end_id:
            tx, ty = end_x, BPMN_START_Y + BPMN_END_EVENT_HEIGHT // 2
        else:
            x, y, w, h = get_pos_and_size(tgt)
            tx, ty = x, y + h // 2

        ET.SubElement(edge, qn(DI_NS, "waypoint"), x=str(int(sx)), y=str(int(sy)))
        ET.SubElement(edge, qn(DI_NS, "waypoint"), x=str(int(tx)), y=str(int(ty)))
    
    all_activities = list(nodes.keys())
    for _, chain in inserted_chains.items():
        all_activities.extend(chain)

    if use_parallel:
        all_activities.append(fork_id)
        all_activities.append(join_id)

    all_activities.append(human_id)

    # Optional: store them in metadata for later reference
    # Had to comment it due to the fact it's not used and the types are not fitting
    # metadata["all_activities"] = all_activities

    # print("All activities in process:", all_activities)

    return ET.tostring(defs, encoding="utf-8", xml_declaration=True).decode("utf-8"), all_activities



async def generate_qrms(quantum_groups: dict[str, list[ImplementationNode]]) -> bytes:
    """
    Generate QRM BPMN files for each quantum node in the provided groups.

    For each quantum node:
    - Create a detector BPMN (quantumCircuitLoadingTask)
    - Create a replacement BPMN (serviceTask with deploymentModelUrl)
    - Package both into a ZIP file named after the node (e.g. node_id.zip)

    Returns:
        dict[str, bytes]: mapping of node_id -> zip file content (bytes)
    """
    

    output_dir = "/tmp/generated_qrms"
    os.makedirs(output_dir, exist_ok=True)

    combined_zip_buffer = io.BytesIO()

    with zipfile.ZipFile(combined_zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as combined_zip:
        for group_id, nodes in quantum_groups.items():
            for node in nodes:
                node_id = getattr(node, "id", "unknown_node")
                node_label = getattr(node, "label", node_id)

                # Detector BPMN
                detector_defs = ET.Element(
                    "bpmn:definitions",
                    {
                        "xmlns:bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
                        "xmlns:bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
                        "xmlns:dc": "http://www.omg.org/spec/DD/20100524/DC",
                        "xmlns:quantme": "https://github.com/UST-QuAntiL/QuantME-Quantum4BPMN",
                        "id": f"Definitions_{uuid.uuid4().hex[:BPMN_FLOW_ID_LENGTH]}",
                        "targetNamespace": "http://bpmn.io/schema/bpmn",
                        "exporter": "QuantME Modeler",
                        "exporterVersion": "4.4.0",
                    },
                )

                process_id = f"Process_{uuid.uuid4().hex[:BPMN_FLOW_ID_LENGTH]}"
                process_el = ET.SubElement(detector_defs, "bpmn:process", {"id": process_id, "isExecutable": "true"})
                detector_task_id = f"Task_{uuid.uuid4().hex[:BPMN_FLOW_ID_LENGTH]}"
                ET.SubElement(
                    process_el,
                    "quantme:quantumCircuitLoadingTask",
                    {"id": detector_task_id, "url": f"{node_label}/maxcut"},
                )

                detector_xml = ET.tostring(detector_defs, encoding="utf-8", xml_declaration=True).decode("utf-8")

                # Replacement BPMN
                executor_defs = ET.Element(
                    "bpmn:definitions",
                    {
                        "xmlns:bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
                        "xmlns:bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
                        "xmlns:dc": "http://www.omg.org/spec/DD/20100524/DC",
                        "xmlns:quantme": "https://github.com/UST-QuAntiL/QuantME-Quantum4BPMN",
                        "id": f"Definitions_{uuid.uuid4().hex[:BPMN_FLOW_ID_LENGTH]}",
                        "targetNamespace": "http://bpmn.io/schema/bpmn",
                        "exporter": "QuantME Modeler",
                        "exporterVersion": "4.5.0-nightly.20211118",
                    },
                )

                executor_process_id = f"Process_{uuid.uuid4().hex[:BPMN_FLOW_ID_LENGTH]}"
                executor_process = ET.SubElement(
                    executor_defs, "bpmn:process", {"id": executor_process_id, "isExecutable": "true"}
                )

                executor_task_id = f"Task_{uuid.uuid4().hex[:BPMN_FLOW_ID_LENGTH]}"
                ET.SubElement(
                    executor_process,
                    "bpmn:serviceTask",
                    {
                        "id": executor_task_id,
                        "name": "Execute OpenQASM",
                        "opentosca:deploymentModelUrl": f"{{{{ wineryEndpoint }}}}/servicetemplates/http%253A%252F%252Fquantil.org%252Fquantme%252Fpull/{node_id}/?csar",
                    },
                )

                executor_xml = ET.tostring(executor_defs, encoding="utf-8", xml_declaration=True).decode("utf-8")

                # Add both BPMN files to the combined ZIP
                combined_zip.writestr(f"Activity_{node_id}/detector.bpmn", detector_xml)
                combined_zip.writestr(f"Activity_{node_id}/replacement.bpmn", executor_xml)

                print(f"[INFO] Added QRM BPMNs for node {node_id} to master ZIP")

    print("[INFO] Combined QRM ZIP generated successfully")
    return combined_zip_buffer.getvalue()
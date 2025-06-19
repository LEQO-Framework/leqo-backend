"""Provides the core logic of the backend."""

from __future__ import annotations

from collections.abc import AsyncIterator
from io import UnsupportedOperation
from typing import Annotated

from fastapi import Depends
from networkx.algorithms.dag import topological_sort
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.enricher import Constraints, Enricher, ParsedImplementationNode
from app.model.CompileRequest import (
    CompileRequest,
    IfThenElseNode,
    ImplementationNode,
    InsertRequest,
    NestedBlock,
    OptimizeSettings,
    RepeatNode,
    SingleInsert,
)
from app.model.CompileRequest import Node as FrontendNode
from app.model.data_types import LeqoSupportedType
from app.openqasm3.printer import leqo_dumps
from app.processing.frontend_graph import FrontendGraph
from app.processing.graph import (
    IOConnection,
    ProcessedProgramNode,
    ProgramGraph,
    ProgramNode,
)
from app.processing.merge import merge_nodes
from app.processing.nested.if_then_else import enrich_if_then_else
from app.processing.nested.repeat import unroll_repeat
from app.processing.nested.utils import generate_pass_node_implementation
from app.processing.optimize import optimize
from app.processing.post import postprocess
from app.processing.pre import preprocess
from app.services import get_db_engine, get_enricher
from app.utils import not_none

TLookup = dict[str, tuple[ProgramNode, FrontendNode]]


class CommonProcessor:
    """Process a :class:`app.processing.frontend_graph.FrontendGraph`.

    :param enricher: The enricher to use to get node implementations
    :frontend_graph: The graph to process
    :optimize_settings: Specify how to optimize the result
    """

    frontend_graph: FrontendGraph
    graph: ProgramGraph
    enricher: Enricher
    optimize: OptimizeSettings
    frontend_to_processed: dict[str, ProcessedProgramNode]

    def __init__(
        self,
        enricher: Enricher,
        frontend_graph: FrontendGraph,
        optimize_settings: OptimizeSettings,
    ) -> None:
        self.enricher = enricher
        self.frontend_graph = frontend_graph
        self.optimize = optimize_settings
        self.graph = ProgramGraph()
        self.frontend_to_processed = {}

    def _resolve_inputs(
        self,
        target_node: str,
        frontend_name_to_index: dict[str, int] | None = None,
    ) -> dict[int, LeqoSupportedType]:
        """Get inputs of current node from previous processed nodes."""
        requested_inputs: dict[int, LeqoSupportedType] = {}
        for source_node in self.frontend_graph.predecessors(target_node):
            source_node_data = not_none(
                self.frontend_to_processed.get(source_node),
                f"Node '{source_node}' should already be enriched",
            )

            for edge in not_none(
                self.frontend_graph.edge_data.get((source_node, target_node)),
                "Edge should exist",
            ):
                output_index = edge.source[1]
                output = source_node_data.io.outputs.get(output_index)
                if output is None:  # https://github.com/python/mypy/issues/17383
                    msg = f"Node '{source_node}' does not define an output with index {output_index}"
                    raise UnsupportedOperation(msg)

                input_index = edge.target[1]
                requested_inputs[input_index] = output.type

                if edge.identifier is None or frontend_name_to_index is None:
                    continue

                frontend_name_to_index[edge.identifier] = input_index

        return requested_inputs


class MergingProcessor(CommonProcessor):
    """Process request with the whole pipeline."""

    @staticmethod
    def from_compile_request(
        request: CompileRequest,
        enricher: Annotated[Enricher, Depends(get_enricher)],
    ) -> MergingProcessor:
        graph = FrontendGraph.create(request.nodes, request.edges)
        return MergingProcessor(enricher, graph, request.metadata)

    async def process_nodes(self) -> None:
        """Process graph by enriching and preprocessing the nodes."""
        for node in topological_sort(self.frontend_graph):
            frontend_node = self.frontend_graph.node_data[node]

            if isinstance(frontend_node, RepeatNode):
                requested_inputs = self._resolve_inputs(node)
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
                if isinstance(frontend_node, IfThenElseNode):
                    frontend_name_to_index: dict[str, int] = {}
                    requested_inputs = self._resolve_inputs(
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
                    requested_inputs = self._resolve_inputs(node)
                    enriched_node = await self.enricher.enrich(
                        frontend_node,
                        Constraints(
                            requested_inputs,
                            optimizeWidth=self.optimize.optimizeWidth is not None,
                            optimizeDepth=self.optimize.optimizeDepth is not None,
                        ),
                    )
                processed_node = preprocess(
                    ProgramNode(node),
                    enriched_node.implementation,
                    requested_inputs,
                )
                self.frontend_to_processed[node] = processed_node
                self.graph.append_node(processed_node)

            for pred in self.frontend_graph.predecessors(node):
                for edge in self.frontend_graph.edge_data[(pred, node)]:
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
        """Convert :class:`app.processing.frontend_graph.FrontendGraph` to :class:`~app.processing.graph.ProgramGraph`.

        This is used as dependency injection for nested nodes.

        :param frontend_graph: The graph to transform
        :return: the enriched + preprocessed graph
        """
        processor = MergingProcessor(self.enricher, frontend_graph, self.optimize)
        await processor.process_nodes()

        if self.optimize.optimizeWidth is not None:
            optimize(self.graph)

        return processor.graph

    async def process(self) -> str:
        """Process the :class:`~app.model.CompileRequest`.

        #. Enrich frontend nodes.
        #. :meth:`~app.processing.pre.preprocess` frontend nodes.
        #. Optionally :meth:`~app.processing.optimize.optimize` graph width.
        #. :meth:`~app.processing.merge.merge_nodes` and
        #. :meth:`~app.processing.post.postprocess` into final program.

        :return: The final QASM program as a string.
        """
        await self.process_nodes()

        if self.optimize.optimizeWidth is not None:
            optimize(self.graph)

        return leqo_dumps(postprocess(merge_nodes(self.graph)))


class EnrichingProcessor(CommonProcessor):
    """Return enrichment for all nodes."""

    @staticmethod
    def from_compile_request(
        request: CompileRequest,
        enricher: Annotated[Enricher, Depends(get_enricher)],
    ) -> EnrichingProcessor:
        graph = FrontendGraph.create(request.nodes, request.edges)
        return EnrichingProcessor(enricher, graph, request.metadata)

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
        """Yield enrichments for nodes in inner block."""
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
        """Yield enrichment of nodes."""
        for node in topological_sort(self.frontend_graph):
            frontend_node = self.frontend_graph.node_data[node]
            requested_inputs = self._resolve_inputs(node)

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
                    requested_inputs = self._resolve_inputs(node)
                    enriched = await self.enricher.enrich(
                        frontend_node,
                        Constraints(
                            requested_inputs,
                            optimizeWidth=self.optimize.optimizeWidth is not None,
                            optimizeDepth=self.optimize.optimizeDepth is not None,
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
        """Get list of all enrichments."""
        return [x async for x in self.enrich()]


class EnrichmentInserter:
    """Insert enrichment implementations for frontend-nodes into the Enricher."""

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
        """Insert all enrichments."""
        async with AsyncSession(self.engine) as session:
            for insert in self.inserts:
                processed = preprocess(ProgramNode(name="dummy"), insert.implementation)
                requested_inputs = {k: v.type for k, v in processed.io.inputs.items()}
                actual_width = processed.qubit.get_width()

                if insert.meta.width is not None and actual_width != insert.meta.width:
                    msg = f"Specified width does not match parsed width: {insert.meta.width} != {actual_width}"
                    raise UnsupportedOperation(msg)
                insert.meta.width = actual_width

                await self.enricher.insert_enrichment(
                    insert.node,
                    insert.implementation,
                    requested_inputs,
                    insert.meta,
                    session,
                )
            await session.commit()

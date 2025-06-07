"""
Provides the core logic of the backend.
"""

from collections.abc import AsyncIterator, Iterable
from typing import Annotated

from fastapi import Depends
from networkx.algorithms.dag import topological_sort
from openqasm3.ast import Program

from app.enricher import Constraints, Enricher, ParsedImplementationNode
from app.model.CompileRequest import (
    CompileRequest,
    Edge,
    IfThenElseNode,
    ImplementationNode,
    OptimizeSettings,
)
from app.model.CompileRequest import Node as FrontendNode
from app.model.data_types import LeqoSupportedType
from app.openqasm3.printer import leqo_dumps
from app.processing.converted_graph import ConvertedProgramGraph
from app.processing.graph import IOConnection, ProgramNode
from app.processing.if_else import enrich_if_else
from app.processing.merge import merge_nodes
from app.processing.optimize import optimize
from app.processing.post import postprocess
from app.processing.pre import preprocess
from app.processing.size_casting import size_cast
from app.services import get_enricher
from app.utils import not_none

TLookup = dict[str, tuple[ProgramNode, FrontendNode]]


class CommonProcessor:
    """
    Handles processing a :class:`~app.processing.graph.ProgramGraph`.
    """

    graph: ConvertedProgramGraph
    enricher: Enricher
    optimize: OptimizeSettings

    def __init__(
        self,
        enricher: Enricher,
        graph: ConvertedProgramGraph,
        optimize_settings: OptimizeSettings,
    ) -> None:
        self.enricher = enricher
        self.graph = graph
        self.optimize = optimize_settings

    def _resolve_inputs(
        self,
        target_node: ProgramNode,
        frontend_name_to_index: dict[str, int],
    ) -> dict[int, LeqoSupportedType]:
        requested_inputs: dict[int, LeqoSupportedType] = {}
        for source_node in self.graph.predecessors(target_node):
            source_node_data = not_none(
                self.graph.node_data.get(source_node),
                f"Node '{source_node.name}' should already be enriched",
            )

            for edge in not_none(
                self.graph.edge_data.get((source_node, target_node)),
                "Edge should exist",
            ):
                if not isinstance(edge, IOConnection):
                    continue

                output_index = edge.source[1]
                output = source_node_data.io.outputs.get(output_index)
                if output is None:  # https://github.com/python/mypy/issues/17383
                    raise Exception(
                        f"Node '{source_node.name}' does not define an output with index {output_index}"
                    )

                input_index = edge.target[1]
                requested_inputs[input_index] = output.type

                if edge.identifier is None:
                    continue

                frontend_name_to_index[edge.identifier] = input_index

        return requested_inputs

    async def _enrich_internal(
        self,
    ) -> AsyncIterator[
        tuple[ProgramNode, ImplementationNode | ParsedImplementationNode]
    ]:
        for target_node in topological_sort(self.graph):
            assert self.graph.node_data.get(target_node) is None

            frontend_name_to_index: dict[str, int] = {}
            requested_inputs = self._resolve_inputs(target_node, frontend_name_to_index)

            _, frontend_node = not_none(
                self.graph.lookup(target_node.name),
                "Lookup should contain all nodes",
            )
            if isinstance(frontend_node, IfThenElseNode):
                enriched_node: (
                    ImplementationNode | ParsedImplementationNode
                ) = await enrich_if_else(
                    frontend_node,
                    requested_inputs,
                    frontend_name_to_index,
                    self._build_inner_graph,
                )
            else:
                enriched_node = await self.enricher.enrich(
                    frontend_node,
                    Constraints(
                        requested_inputs,
                        optimizeWidth=self.optimize.optimizeWidth is not None,
                        optimizeDepth=self.optimize.optimizeDepth is not None,
                    ),
                )
            processed_node = preprocess(target_node, enriched_node.implementation)
            size_cast(
                processed_node,
                {index: type.bit_size for index, type in requested_inputs.items()},
            )
            self.graph.node_data[target_node] = processed_node

            yield target_node, enriched_node

    def _process_internal(self) -> Program:
        if self.optimize.optimizeWidth is not None:
            optimize(self.graph)

        program = merge_nodes(self.graph)
        return postprocess(program)

    async def _build_inner_graph(
        self,
        nodes: Iterable[FrontendNode | ParsedImplementationNode],
        edges: Iterable[Edge],
    ) -> ConvertedProgramGraph:
        graph = ConvertedProgramGraph.create(nodes, edges)

        processor = CommonProcessor(self.enricher, graph, self.optimize)
        async for _ in processor._enrich_internal():
            pass

        if self.optimize.optimizeWidth is not None:
            optimize(self.graph)

        return graph


class Processor(CommonProcessor):
    """
    Handles processing a :class:`~app.model.CompileRequest.CompileRequest`.
    """

    def __init__(
        self,
        request: CompileRequest,
        enricher: Annotated[Enricher, Depends(get_enricher)],
    ) -> None:
        graph = ConvertedProgramGraph.create(request.nodes, request.edges)

        super().__init__(enricher, graph, request.metadata)

    async def enrich(
        self,
    ) -> AsyncIterator[ImplementationNode | ParsedImplementationNode]:
        """
        Enriches the :class:`~app.model.CompileRequest`.

        :return: Iteration of enriched nodes.
        """

        async for _, enriched_node in self._enrich_internal():
            yield enriched_node

    async def process(self) -> str:
        """
        Process the :class:`~app.model.CompileRequest`.

        #. Enrich frontend nodes.
        #. :meth:`~app.processing.pre.preprocess` frontend nodes.
        #. Optionally :meth:`~app.processing.optimize.optimize` graph width.
        #. :meth:`~app.processing.merge.merge_nodes` and
        #. :meth:`~app.processing.post.postprocess` into final program.

        :return: The final QASM program as a string.
        """

        # Enrich all nodes
        async for _ in self._enrich_internal():
            pass

        program = self._process_internal()
        return leqo_dumps(program)

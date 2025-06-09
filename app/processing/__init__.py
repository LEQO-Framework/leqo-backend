"""
Provides the core logic of the backend.
"""

from collections.abc import AsyncIterator, Iterable
from typing import Annotated

from fastapi import Depends
from networkx.algorithms.dag import topological_sort

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
from app.processing.frontend_graph import FrontendGraph
from app.processing.graph import (
    IOConnection,
    ProcessedProgramNode,
    ProgramGraph,
    ProgramNode,
)
from app.processing.merge import merge_nodes
from app.processing.nested.if_then_else import enrich_if_then_else
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
                    raise Exception(
                        f"Node '{source_node}' does not define an output with index {output_index}"
                    )

                input_index = edge.target[1]
                requested_inputs[input_index] = output.type

                if edge.identifier is None or frontend_name_to_index is None:
                    continue

                frontend_name_to_index[edge.identifier] = input_index

        return requested_inputs

    async def enrich(
        self,
    ) -> AsyncIterator[ImplementationNode | ParsedImplementationNode]:
        for node in topological_sort(self.frontend_graph):
            frontend_node = self.frontend_graph.node_data[node]

            if isinstance(frontend_node, IfThenElseNode):
                frontend_name_to_index: dict[str, int] = {}
                requested_inputs = self._resolve_inputs(node, frontend_name_to_index)
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
            processed_node = preprocess(ProgramNode(node), enriched_node.implementation)
            size_cast(
                processed_node,
                {index: type.size for index, type in requested_inputs.items()},
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

            yield enriched_node

    async def _build_inner_graph(
        self,
        nodes: Iterable[FrontendNode | ParsedImplementationNode],
        edges: Iterable[Edge],
    ) -> ProgramGraph:
        processor = CommonProcessor(
            self.enricher, FrontendGraph.create(nodes, edges), self.optimize
        )
        async for _ in processor.enrich():
            pass

        if self.optimize.optimizeWidth is not None:
            optimize(self.graph)

        return processor.graph


class Processor(CommonProcessor):
    """
    Handles processing a :class:`~app.model.CompileRequest.CompileRequest`.
    """

    def __init__(
        self,
        request: CompileRequest,
        enricher: Annotated[Enricher, Depends(get_enricher)],
    ) -> None:
        graph = FrontendGraph.create(request.nodes, request.edges)

        super().__init__(enricher, graph, request.metadata)

    async def enrich_all(self) -> list[ImplementationNode]:
        result_list: list[ImplementationNode] = []

        for enriched in [x async for x in self.enrich()]:
            if isinstance(enriched, ParsedImplementationNode):
                result_list.append(
                    ImplementationNode(
                        id=enriched.id,
                        label=enriched.label,
                        implementation=leqo_dumps(enriched.implementation),
                    )
                )
            else:
                result_list.append(enriched)

        return result_list

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
        async for _ in self.enrich():
            pass

        if self.optimize.optimizeWidth is not None:
            optimize(self.graph)

        return leqo_dumps(postprocess(merge_nodes(self.graph)))

"""
Provides the core logic of the backend.
"""

from collections.abc import AsyncIterator

from networkx.algorithms.dag import topological_sort

from app.enricher import Constraints, Enricher
from app.model.CompileRequest import CompileRequest, ImplementationNode
from app.model.CompileRequest import Node as FrontendNode
from app.model.data_types import LeqoSupportedType
from app.openqasm3.printer import leqo_dumps
from app.processing.graph import IOConnection, ProgramGraph, ProgramNode
from app.processing.merge import merge_nodes
from app.processing.optimize import optimize
from app.processing.post import postprocess
from app.processing.pre import preprocess
from app.utils import not_none


class Processor:
    """
    Handles processing a :class:`~app.model.CompileRequest.CompileRequest`.
    """

    request: CompileRequest
    graph: ProgramGraph
    lookup: dict[str, tuple[ProgramNode, FrontendNode]]
    enricher: Enricher

    def __init__(self, request: CompileRequest, enricher: Enricher):
        self.request = request
        self.enricher = enricher
        self.graph = ProgramGraph()
        self.lookup = {}

        for frontend_node in self.request.nodes:
            program_node = ProgramNode(frontend_node.id)
            self.lookup[frontend_node.id] = (program_node, frontend_node)
            self.graph.add_node(program_node)

        for edge in self.request.edges:
            self.graph.append_edge(
                IOConnection(
                    (self.lookup[edge.source[0]][0], edge.source[1]),
                    (self.lookup[edge.target[0]][0], edge.target[1]),
                )
            )

    def _resolve_inputs(self, target_node: ProgramNode) -> dict[int, LeqoSupportedType]:
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

        return requested_inputs

    async def _enrich_internal(
        self,
    ) -> AsyncIterator[tuple[ProgramNode, ImplementationNode]]:
        for target_node in topological_sort(self.graph):
            assert self.graph.node_data.get(target_node) is None

            requested_inputs = self._resolve_inputs(target_node)

            _, frontend_node = not_none(
                self.lookup.get(target_node.name), "Lookup should contain all nodes"
            )
            enriched_node = await self.enricher.enrich(
                frontend_node,
                Constraints(
                    requested_inputs,
                    optimizeWidth=self.request.metadata.optimizeWidth is not None,
                    optimizeDepth=self.request.metadata.optimizeDepth is not None,
                ),
            )

            self.graph.node_data[target_node] = preprocess(
                target_node, enriched_node.implementation
            )

            yield target_node, enriched_node

    async def enrich(self) -> AsyncIterator[ImplementationNode]:
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

        if self.request.metadata.optimizeWidth is not None:
            optimize(self.graph)

        program = merge_nodes(self.graph)
        program = postprocess(program)
        return leqo_dumps(program)

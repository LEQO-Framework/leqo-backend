"""
Provides the core logic of the backend.
"""

from networkx.algorithms.dag import topological_sort

from app.enricher import Constraints, Enricher
from app.model.CompileRequest import CompileRequest
from app.model.CompileRequest import Node as FrontendNode
from app.model.data_types import LeqoSupportedType
from app.openqasm3.printer import leqo_dumps
from app.processing.graph import (
    IOConnection,
    ProgramGraph,
    ProgramNode,
)
from app.processing.merge import merge_nodes
from app.processing.optimize import optimize
from app.processing.post import postprocess
from app.processing.pre import preprocess


class _Processor:
    request: CompileRequest
    graph: ProgramGraph
    lookup: dict[str, tuple[ProgramNode, FrontendNode]]
    enricher: Enricher

    def __init__(self, request: CompileRequest):
        self.request = request
        self.graph = ProgramGraph()
        self.lookup = {}

    async def process(self) -> str:
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

        if self.request.metadata.optimizeWidth is not None:
            optimize(self.graph)

        program = merge_nodes(self.graph)
        program = postprocess(program)
        return leqo_dumps(program)

    async def _enrich_graph(self) -> None:
        for target_node in topological_sort(self.graph):
            assert self.graph.node_data.get(target_node) is None, ""

            _, frontend_node = self.lookup[target_node.name]

            requested_inputs: dict[int, LeqoSupportedType] = {}
            for source_node in self.graph.predecessors(target_node):
                source_node_data = self.graph.node_data[source_node]
                for edge in self.graph.edge_data[(source_node, target_node)]:
                    if not isinstance(edge, IOConnection):
                        continue

                    output_index = edge.source[1]
                    input_index = edge.target[1]

                    requested_inputs[input_index] = source_node_data.io.outputs[
                        output_index
                    ].type

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


async def process(body: CompileRequest) -> str:
    """
    Process the :class:`~app.model.CompileRequest`.

    #. :meth:`~app.processing.pre.preprocess` frontend nodes.
    #. Optionally :meth:`~app.processing.optimize.optimize` graph width.
    #. :meth:`~app.processing.merge.merge_nodes` and
    #. :meth:`~app.processing.post.postprocess` into final program.

    :param body: CompileRequest
    :return: The final QASM program as a string.
    """
    processor = _Processor(body)
    return await processor.process()

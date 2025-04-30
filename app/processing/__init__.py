"""
Provides the core logic of the backend.
"""

from app.model.CompileRequest import (
    CompileRequest,
    ImplementationNode,
)
from app.model.CompileRequest import (
    Node as FrontendNode,
)
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

    def __init__(self, request: CompileRequest):
        self.request = request
        self.graph = ProgramGraph()
        self.lookup = {}

    def process(self) -> str:
        for frontend_node in self.request.nodes:
            if not isinstance(frontend_node, ImplementationNode):
                raise TypeError(
                    f"Type of node {frontend_node.id} must be ImplementationNode"
                )

            program_node = ProgramNode(frontend_node.id)
            self.lookup[frontend_node.id] = (program_node, frontend_node)

            self.graph.append_node(
                preprocess(program_node, frontend_node.implementation)
            )

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


def process(body: CompileRequest) -> str:
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
    return processor.process()

"""Optimize the modeled graph by adding additional ancilla connections and decide whether to uncompute."""

from copy import deepcopy

from openqasm3.ast import BranchingStatement, QASMNode, Statement

from app.openqasm3.visitor import LeqoTransformer
from app.processing.graph import ProgramGraph
from app.processing.optimize.algos import NoPredCheckNeedDiffScore


class ApplyUncomputeTransformer(LeqoTransformer[None]):
    """Enable or remove uncompute-blocks in visited AST."""

    enable: bool

    def __init__(self, enable: bool) -> None:
        super().__init__()
        self.enable = enable

    def visit_BranchingStatement(
        self,
        node: BranchingStatement,
    ) -> QASMNode | None | list[Statement]:
        uncompute_block = False
        for annotation in node.annotations:
            if annotation.keyword.startswith("leqo.uncompute"):
                uncompute_block = True
        if not uncompute_block:
            return node
        if not self.enable:
            return None
        return node.if_block


def optimize(graph: ProgramGraph) -> None:
    """Optimize the given graph in-place based on :class:`app.processing.graph.IOInfo`.

    :param graph: Graph of all nodes representing the program
    """
    ancilla_edges, uncomputes = NoPredCheckNeedDiffScore(deepcopy(graph)).compute()
    for edge in ancilla_edges:
        graph.append_edge(edge)

    for raw_node in graph.nodes:
        node = graph.get_data_node(raw_node)
        node.implementation = ApplyUncomputeTransformer(uncomputes[raw_node]).visit(
            node.implementation,
        )

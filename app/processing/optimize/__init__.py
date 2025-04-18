"""Optimize the modelled graph be adding additional ancilla connections and decide whether to uncompute."""

from abc import ABC, abstractmethod
from copy import deepcopy

from openqasm3.ast import BooleanLiteral, BranchingStatement, QASMNode

from app.openqasm3.visitor import LeqoTransformer
from app.processing.graph import AncillaConnection, ProgramGraph, ProgramNode
from app.processing.optimize.no_pred import NoPredCheckNeedDiffScore


class OptimizationAlgo(ABC):
    """Interface for optimization algorithms."""

    graph: ProgramGraph

    def __init__(self, graph: ProgramGraph) -> None:
        self.graph = graph

    @abstractmethod
    def compute(self) -> tuple[list[AncillaConnection], dict[ProgramNode, bool]]:
        pass


class EnableUncomputeTransformer(LeqoTransformer[None]):
    def visit_BranchingStatement(self, node: BranchingStatement) -> QASMNode:
        uncompute_block = False
        for annotation in node.annotations:
            if annotation.keyword.startswith("leqo.uncompute"):
                uncompute_block = True
        if not uncompute_block:
            return node
        node.condition = BooleanLiteral(True)
        return node


def optimize(graph: ProgramGraph) -> None:
    """Optimize the given graph in-place based on :class:`app.processing.graph.IOInfo`.

    :param graph: Graph of all nodes representing the program
    """
    ancilla_edges, uncomputes = NoPredCheckNeedDiffScore(deepcopy(graph)).compute()
    for edge in ancilla_edges:
        graph.append_edge(edge)

    for raw_node in graph.nodes:
        if not uncomputes[raw_node]:
            continue
        node = graph.get_data_node(raw_node)
        node.implementation = EnableUncomputeTransformer().visit(node.implementation)

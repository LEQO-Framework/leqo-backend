"""Optimize the modelled graph be adding additional ancilla connections and decide whether to uncompute."""

from abc import ABC, abstractmethod
from copy import deepcopy

from app.processing.graph import AncillaConnection, ProgramGraph, ProgramNode
from app.processing.optimize.no_pred import NoPredCheckNeed


class OptimizationAlgo(ABC):
    """Interface for optimization algorithms."""

    graph: ProgramGraph

    def __init__(self, graph: ProgramGraph) -> None:
        self.graph = graph

    @abstractmethod
    def compute(self) -> tuple[list[AncillaConnection], dict[ProgramNode, bool]]:
        pass


def optimize(graph: ProgramGraph) -> None:
    """Optimize the given graph in-place based on :class:`app.processing.graph.IOInfo`.

    :param graph: Graph of all nodes representing the program
    """
    ancilla_edges, uncomputes = NoPredCheckNeed(deepcopy(graph)).compute()
    # TODO: apply this

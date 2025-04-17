"""Optimize the modelled graph be adding additional ancilla connections and decide whether to uncompute."""

from app.processing.graph import ProgramGraph


def optimize(graph: ProgramGraph) -> None:
    """Optimize the given graph in-place based on :class:`app.processing.graph.IOInfo`.

    :param graph: Graph of all nodes representing the program
    """
    # not implemented yet

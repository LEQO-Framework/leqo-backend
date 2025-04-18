"""
Provides the core logic of the backend.
"""

from openqasm3.ast import Program

from app.processing.graph import (
    ProcessedProgramNode,
    ProgramGraph,
    ProgramNode,
)
from app.processing.merge import merge_nodes as merge_impl
from app.processing.optimize import optimize as optimize_impl
from app.processing.post import postprocess
from app.processing.pre import preprocess as preprocess_impl


def preprocess(node: ProgramNode) -> ProcessedProgramNode:
    """Preprocess the given node.

    :param node: Node to preprocess
    :return: Preprocessed node
    """
    return preprocess_impl(node)


def merge_nodes(graph: ProgramGraph) -> Program:
    """Create a unified :class:`openqasm3.ast.Program` from a modelled graph with attached qasm implementation snippets.

    :param graph: Graph of all nodes representing the program
    :return: The unified qasm program
    """
    optimize_impl(graph)
    merged_program = merge_impl(graph)
    return postprocess(merged_program)

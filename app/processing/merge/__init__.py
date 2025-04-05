from networkx import topological_sort
from openqasm3.ast import Pragma, Program, Statement

from app.openqasm3.ast import CommentStatement
from app.processing.graph import ProgramGraph
from app.processing.post import postprocess


def merge_nodes(graph: ProgramGraph) -> Program:
    """Create a unified :class:`openqasm3.ast.Program` from a modelled graph with attached qasm implementation snippets.

    :param graph: Graph of all nodes representing the program
    :return: The unified qasm program
    """
    all_statements: list[Statement | Pragma] = []

    # TODO: this does not sort the nodes the right way, this will need io-info
    for node in topological_sort(graph):
        all_statements.append(CommentStatement(f"Start node {node.name}"))

        all_statements.extend(graph.get_data_node(node).implementation.statements)

        all_statements.append(CommentStatement(f"End node {node.name}"))

    merged_program = Program(all_statements, version="3.1")
    return postprocess(merged_program)

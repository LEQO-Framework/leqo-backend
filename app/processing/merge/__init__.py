"""
Merge all nodes of the :class:`app.processing.graph.ProgramGraph` into a single QASM program.
"""

from networkx import topological_sort
from openqasm3.ast import (
    Identifier,
    IntegerLiteral,
    Pragma,
    Program,
    QubitDeclaration,
    Statement,
)

from app.openqasm3.ast import CommentStatement
from app.processing.graph import ProgramGraph
from app.processing.merge.connections import connect_qubits
from app.processing.post import postprocess

GLOBAL_REG_NAME = "leqo_reg"


def merge_nodes(graph: ProgramGraph) -> Program:
    """Create a unified :class:`openqasm3.ast.Program` from a modelled graph with attached qasm implementation snippets.

    :param graph: Graph of all nodes representing the program
    :return: The unified qasm program
    """
    reg_size = connect_qubits(graph, GLOBAL_REG_NAME)

    all_statements: list[Statement | Pragma] = [
        QubitDeclaration(Identifier(GLOBAL_REG_NAME), IntegerLiteral(reg_size)),
    ]

    for node in topological_sort(graph):
        all_statements.append(CommentStatement(f"Start node {node.name}"))

        all_statements.extend(graph.get_data_node(node).implementation.statements)

        all_statements.append(CommentStatement(f"End node {node.name}"))

    merged_program = Program(all_statements, version="3.1")
    return postprocess(merged_program)

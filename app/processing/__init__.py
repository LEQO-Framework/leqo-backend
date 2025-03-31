from io import StringIO

from openqasm3.ast import Pragma, Program, Statement

from app.openqasm3.ast import CommentStatement
from app.openqasm3.printer import LeqoPrinter
from app.processing.graph import ProgramNode, SectionInfo
from app.processing.post import postprocess
from app.processing.pre import preprocess


def merge_nodes(nodes: set[ProgramNode], connections: set[IOConnection]) -> Program:
    """Create a unified :class:`openqasm3.ast.Program` from a modelled graph with attached qasm implementation snippets.

    :param graph: Visual model of the qasm program
    :return: The unifed qasm program
    """

    all_statements: list[Statement | Pragma] = []

    # TODO: This can be parallelized
    # TODO: this does not sort the nodes the right way, this will need io-info
    for i, node in enumerate(nodes):
        all_statements.append(CommentStatement(f"Start node {node.id}"))

        ast = preprocess(node.implementation.ast, SectionInfo(i, node))
        all_statements.extend(ast.statements)

        all_statements.append(CommentStatement(f"End node {node.id}"))

    merged_program = Program(all_statements, version="3.1")
    return postprocess(merged_program)


def print_program(program: Program) -> str:
    """
    Prints the given program as a string.

    :param program: The program to print
    :return: The program as a string
    """

    result = StringIO()
    LeqoPrinter(result).visit(program)
    return result.getvalue()

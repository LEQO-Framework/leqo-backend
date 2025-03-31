from graphlib import TopologicalSorter
from io import StringIO

from openqasm3.ast import Pragma, Program, Statement

from app.openqasm3.ast import CommentStatement
from app.openqasm3.printer import LeqoPrinter
from app.processing.graph import IOConnection, ProgramNode, SectionInfo
from app.processing.post import postprocess
from app.processing.pre import preprocess


def merge_nodes(nodes: set[ProgramNode], edges: set[IOConnection]) -> Program:
    """Create a unified :class:`openqasm3.ast.Program` from a modelled graph with attached qasm implementation snippets.

    :param nodes: set containing the program snippets
    :param connections: set containing the input/output connections
    :return: The unifed qasm program
    """
    all_statements: list[Statement | Pragma] = []
    topologie: TopologicalSorter[ProgramNode] = TopologicalSorter()
    for node in nodes:
        topologie.add(node)

    for edge in edges:
        topologie.add(edge.target[0], edge.source[0])

    # TODO: This can be parallelized
    # TODO: this does not sort the nodes the right way, this will need io-info
    for i, node in enumerate(topologie.static_order()):
        all_statements.append(CommentStatement(f"Start node {node.id}"))

        ast = preprocess(node.implementation.ast, SectionInfo(i, node))
        all_statements.extend(ast.statements)

        all_statements.append(CommentStatement(f"End node {node.id}"))

    merged_program = Program(all_statements, version="3.1")
    return postprocess(merged_program)


def print_program(program: Program) -> str:
    """Prints the given program as a string.

    :param program: The program to print
    :return: The program as a string
    """
    result = StringIO()
    LeqoPrinter(result).visit(program)
    return result.getvalue()

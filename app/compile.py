from graphlib import TopologicalSorter
from io import StringIO

from openqasm3.ast import Pragma, Program, Statement
from openqasm3.parser import parse

from app.model.ModelNode import ModelNode
from app.model.SectionInfo import SectionInfo
from app.openqasm3.ast import CommentStatement
from app.openqasm3.printer import LeqoPrinter
from app.postprocessing import postprocess
from app.preprocessing import preprocess


def parse_qasm(qasm: str) -> Program:
    """
    Parses an openqasm2 or openqasm3 string into an ast (:class:`~openqasm3.ast.Program`)

    :param qasm: The qasm string to parse
    :return: The parse ast
    """

    # ToDo: Check for openqasm2 and wire converter
    return parse(qasm)


def parse_qasm_nullable(qasm: str | None) -> Program | None:
    if qasm is None:
        return None

    return parse_qasm(qasm)


def merge_nodes(graph: TopologicalSorter[ModelNode]) -> Program:
    """
    Creates a unified :class:`openqasm3.ast.Program` from a modelled graph with attached qasm implementation snippets.

    :param graph: Visual model of the qasm program
    :return: The unifed qasm program
    """

    all_statements: list[Statement | Pragma] = []

    # ToDo: This can be parallelized
    for i, node in enumerate(graph.static_order()):
        all_statements.append(CommentStatement(f"Start node {node.id}"))

        ast = preprocess(node.Implementation, SectionInfo(i))
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

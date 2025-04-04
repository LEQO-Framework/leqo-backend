from io import StringIO
from uuid import uuid4

from openqasm3.ast import Program

from app.openqasm3.parser import leqo_parse
from app.openqasm3.printer import LeqoPrinter
from app.processing.graph import (
    ProcessedProgramNode,
    ProgramGraph,
    ProgramNode,
    SectionInfo,
)
from app.processing.merge import merge_nodes as merge_impl
from app.processing.post import postprocess
from app.processing.pre import preprocess as preprocess_impl
from app.utils import opt_call


def preprocess(node: ProgramNode) -> ProcessedProgramNode:
    """
    Preprocess the given node.

    :param node: Node to preprocess
    :return: Preprocessed node
    """

    section_info = SectionInfo(uuid4())
    implementation = preprocess_impl(leqo_parse(node.implementation), section_info)

    uncompute_implementation = opt_call(leqo_parse, node.uncompute_implementation)

    return ProcessedProgramNode(
        node, implementation, section_info, uncompute_implementation
    )


def merge_nodes(graph: ProgramGraph) -> Program:
    """Create a unified :class:`openqasm3.ast.Program` from a modelled graph with attached qasm implementation snippets.

    :param graph: Graph of all nodes representing the program
    :return: The unified qasm program
    """
    merged_program = merge_impl(graph)
    return postprocess(merged_program)


def print_program(program: Program) -> str:
    """Prints the given program as a string.

    :param program: The program to print
    :return: The program as a string
    """
    result = StringIO()
    LeqoPrinter(result).visit(program)
    return result.getvalue()

"""Each qasm snippet attached to a node in the editor will first be passed through the preprocessing pipeline.

The pipeline consists of multiple :class:`~openqasm3.visitor.QASMTransformer` that will transform the abstract syntax tree (AST) of the qasm snippet.
"""

from openqasm3.ast import Program

from app.processing.graph import IOInfo, ProcessedProgramNode, ProgramNode, QubitInfo
from app.processing.pre.converter import parse_to_openqasm3
from app.processing.pre.inlining import InliningTransformer
from app.processing.pre.io_parser import ParseAnnotationsVisitor
from app.processing.pre.renaming import RenameRegisterTransformer
from app.processing.utils import cast_to_program


def preprocess(
    node: ProgramNode, implementation: str | Program
) -> ProcessedProgramNode:
    """Run an openqasm3 snippet through the preprocessing pipeline.

    :param node: The node to preprocess.
    :param implementation: A valid OpenQASM 2/3 implementation for that node.
    :return: The preprocessed program.
    """
    if isinstance(implementation, Program):
        ast = implementation
    else:
        ast = parse_to_openqasm3(implementation)
    ast = RenameRegisterTransformer().visit(ast, node.id)
    ast = cast_to_program(InliningTransformer().visit(ast))

    io = IOInfo()
    qubit = QubitInfo()
    _ = ParseAnnotationsVisitor(io, qubit).visit(ast)

    return ProcessedProgramNode(node, ast, io, qubit)

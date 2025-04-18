"""
Each qasm snippet attached to a node in the editor will first be passed through the preprocessing pipeline.
The pipeline consists of multiple :class:`~openqasm3.visitor.QASMTransformer` that will transform the abstract syntax tree (AST) of the qasm snippet.
"""

from uuid import uuid4

from app.openqasm3.parser import leqo_parse
from app.processing.graph import IOInfo, ProcessedProgramNode, ProgramNode, QubitInfo
from app.processing.pre.inlining import InliningTransformer
from app.processing.pre.io_parser import ParseAnnotationsVisitor
from app.processing.pre.renaming import RenameRegisterTransformer
from app.processing.utils import cast_to_program


def preprocess(node: ProgramNode, implementation: str) -> ProcessedProgramNode:
    """Run an openqasm3 snippet through the preprocessing pipeline.

    :param program: A valid openqasm3 program (as AST) to preprocess.
    :param section_info: MetaData of the section to preprocess.
    :return: The preprocessed program.
    """
    ast = leqo_parse(implementation)
    ast = RenameRegisterTransformer().visit(ast, node.id)
    ast = cast_to_program(InliningTransformer().visit(ast))

    io = IOInfo()
    qubit = QubitInfo()
    _ = ParseAnnotationsVisitor(io, qubit).visit(ast)

    return ProcessedProgramNode(node, ast, io, qubit)

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


def preprocess(node: ProgramNode) -> ProcessedProgramNode:
    """Run an openqasm3 snippet through the preprocessing pipeline.

    :param program: A valid openqasm3 program (as AST) to preprocess.
    :param section_info: MetaData of the section to preprocess.
    :return: The preprocessed program.
    """
    id = uuid4()
    implementation = leqo_parse(node.implementation)
    implementation = RenameRegisterTransformer().visit(implementation, id)
    implementation = cast_to_program(InliningTransformer().visit(implementation))

    io = IOInfo()
    qubit = QubitInfo()
    _ = ParseAnnotationsVisitor(io, qubit).visit(implementation)

    return ProcessedProgramNode(node, implementation, id, io, qubit)

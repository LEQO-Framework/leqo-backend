"""
Each qasm snippet attached to a node in the editor will first be passed through the preprocessing pipeline.
The pipeline consists of multiple :class:`~openqasm3.visitor.QASMTransformer` that will transform the abstract syntax tree (AST) of the qasm snippet.
"""

from openqasm3.ast import Program

from app.processing.graph import SectionInfo
from app.processing.pre.inlining import InliningTransformer
from app.processing.pre.renaming import RenameRegisterTransformer


def preprocess(program: Program, section_info: SectionInfo) -> Program:
    """
    Runs an openqasm3 snippet through the preprocessing pipeline.

    :param program: A valid openqasm3 program (as AST) to preprocess.
    :param section_info: MetaData of the section to preprocess.
    :return: The preprocessed program.
    """

    program = RenameRegisterTransformer().visit(program, section_info)
    program = InliningTransformer().visit(program, section_info)
    return program  # noqa: RET504 # Ignore because QASMTransformer.visit returns Any

from openqasm3.ast import Program

from app.processing.graph import SectionInfo
from app.processing.pre.inlining import InliningTransformer
from app.processing.pre.io_parser import IOParse
from app.processing.pre.renaming import RenameRegisterTransformer
from app.processing.utils import cast_to_program


def preprocess(program: Program, section_info: SectionInfo) -> Program:
    """Run an openqasm3 snippet through the preprocessing pipeline.

    :param program: A valid openqasm3 program (as AST) to preprocess.
    :param section_info: MetaData of the section to preprocess.
    :return: The preprocessed program.
    """
    program = RenameRegisterTransformer().visit(program, section_info)
    program = InliningTransformer().visit(program, section_info)
    return cast_to_program(IOParse(section_info.io).visit(program))

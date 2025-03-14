from openqasm3.ast import Program
from openqasm3.parser import parse

from app.model.SectionInfo import SectionInfo
from app.preprocessing.inlining import InliningTransformer
from app.preprocessing.renaming import RenameRegisterTransformer


def preprocess_str(program_raw: str, section_info: SectionInfo) -> Program:
    """
    Runs an openqasm3 program through the preprocessing pipeline.

    :param program_raw: A valid openqasm3 program (as string) to preprocess.
    :param section_info: MetaData of the section to preprocess.
    :return: The preprocessed program.
    """

    program = parse(program_raw)
    return preprocess(program, section_info)


def preprocess(program: Program, section_info: SectionInfo) -> Program:
    """
    Runs an openqasm3 snippet through the preprocessing pipeline.

    :param program: A valid openqasm3 program (as AST) to preprocess.
    :param section_info: MetaData of the section to preprocess.
    :return: The preprocessed program.
    """

    program = InliningTransformer().visit(program, section_info)
    program = RenameRegisterTransformer().visit(program, section_info)
    return program  # noqa: RET504 # Ignore because QASMTransformer.visit returns Any

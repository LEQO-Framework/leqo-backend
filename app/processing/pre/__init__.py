from openqasm3.ast import Program, QASMNode

from app.processing.graph import SectionInfo
from app.processing.pre.io_parser import IOParse
from app.processing.pre.renaming import RenameRegisterTransformer


def preprocess(program: Program, section_info: SectionInfo) -> Program:
    """Run an openqasm3 snippet through the preprocessing pipeline.

    :param program: A valid openqasm3 program (as AST) to preprocess.
    :param section_info: MetaData of the section to preprocess.
    :return: The preprocessed program.
    """

    def to_program(node: QASMNode | None) -> Program:
        """Cast to Program or raise error."""
        if not isinstance(node, Program):
            msg = f"Tried to cast {type(node)} to Program."
            raise TypeError(msg)
        return node

    program = to_program(RenameRegisterTransformer().visit(program, section_info))
    program = to_program(IOParse(section_info.io).visit(program))
    return program

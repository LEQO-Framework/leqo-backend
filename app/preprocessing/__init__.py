from openqasm3.ast import Program
from openqasm3.parser import parse

from app.model.SectionInfo import SectionInfo
from app.preprocessing.inlining import InliningTransformer
from app.preprocessing.memory import MemoryTransformer
from app.preprocessing.renaming import RenameRegisterTransformer


def preprocess_str(program_raw: str, stage_index: int) -> Program:
    program = parse(program_raw)
    return preprocess(program, stage_index)


def preprocess(program: Program, stage_index: int) -> Program:
    section_info = SectionInfo(stage_index, globals={})

    program = InliningTransformer().visit(program, section_info)
    program = RenameRegisterTransformer().visit(program, section_info)
    program = MemoryTransformer().visit(program, section_info)
    return program  # noqa: RET504 # Ignore because QASMTransformer.visit returns Any

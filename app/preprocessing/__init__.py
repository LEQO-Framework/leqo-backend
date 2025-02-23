from openqasm3.ast import Program
from openqasm3.parser import parse

from app.preprocessing.inlining import InliningTransformer
from app.preprocessing.renaming import RenameRegisterTransformer


def preprocess_str(program_raw: str, stage_index: int) -> Program:
    program = parse(program_raw)
    return preprocess(program, stage_index)


def preprocess(program: Program, stage_index: int) -> Program:
    program = InliningTransformer().visit(program)
    program = RenameRegisterTransformer(stage_index).visit(program)
    return program  # noqa: RET504 # Ignore because QASMTransformer.visit returns Any

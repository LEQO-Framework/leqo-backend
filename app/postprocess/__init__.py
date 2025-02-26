from openqasm3.ast import Program
from openqasm3.parser import parse

from app.postprocess.imports import Imports


def preprocess_str(program_raw: str) -> Program:
    program = parse(program_raw)
    return preprocess(program)


def preprocess(program: Program) -> Program:
    program = Imports().visit(program)
    return program

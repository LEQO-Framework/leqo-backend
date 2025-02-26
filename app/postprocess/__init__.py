from openqasm3.ast import Program
from openqasm3.printer import dumps

from app.postprocess.sort_imports import SortImports
from app.postprocess.unique_declarations import UniqueDeclarations


def preprocess_str(program: Program) -> str:
    return dumps(preprocess(program))


def preprocess(program: Program) -> Program:
    program = SortImports().transform(program)
    return UniqueDeclarations().transform(program)

from openqasm3.ast import Program, QASMNode
from openqasm3.printer import dumps

from app.postprocess.sort_imports import SortImports
from app.postprocess.unique_declarations import UniqueDeclarations


def preprocess_str(program: Program) -> str:
    return dumps(preprocess(program))


def preprocess(program: Program) -> Program:
    tmp: QASMNode | None = None
    for Transformer in (SortImports, UniqueDeclarations):
        tmp = Transformer().visit(program)
        if not isinstance(tmp, Program):
            raise RuntimeError(f"{Transformer} returned {tmp}, not a Program")
        program = tmp
    return program

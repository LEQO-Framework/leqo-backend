"""Post-process merged QASM-Program."""

from openqasm3.ast import Program, QASMNode
from openqasm3.printer import dumps

from app.postprocess.sort_imports import SortImports


def preprocess_str(program: Program) -> str:
    """Return post-processed program as string."""
    return dumps(preprocess(program))


def preprocess(program: Program) -> Program:
    """Return post-processed program as AST."""
    tmp: QASMNode | None = None
    for transformer in (SortImports,):
        tmp = transformer().visit(program)
        if not isinstance(tmp, Program):
            msg = f"{transformer} returned {tmp}, not a Program"
            raise TypeError(msg)
        program = tmp
    return program

"""Post-process merged QASM-Program."""

from openqasm3.ast import Program

from app.processing.post.sort_imports import SortImports
from app.processing.utils import cast_to_program


def postprocess(program: Program) -> Program:
    """Return post-processed program as AST."""
    return cast_to_program(SortImports().visit(program))

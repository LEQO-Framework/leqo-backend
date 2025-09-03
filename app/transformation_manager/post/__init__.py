"""
Post-process merged QASM-Program.

Currently, this does only sort imports.
"""

from openqasm3.ast import Program

from app.processing.post.sort_imports import SortImportsTransformer
from app.processing.utils import cast_to_program


def postprocess(program: Program) -> Program:
    """
    Return post-processed program as AST.
    """
    return cast_to_program(SortImportsTransformer().visit(program))

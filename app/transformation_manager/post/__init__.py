"""
Post-process merged QASM-Program.
"""

from collections.abc import Iterable

from openqasm3.ast import Program

from app.transformation_manager.post.qiskit_compat import apply_qiskit_compatibility
from app.transformation_manager.post.sort_imports import SortImportsTransformer
from app.transformation_manager.utils import cast_to_program


def postprocess(
    program: Program,
    *,
    qiskit_compat: bool = False,
    literal_nodes: Iterable[str] | None = None,
    literal_nodes_with_consumers: Iterable[str] | None = None,
) -> Program:
    """
    Return post-processed program as AST.
    """
    processed = program
    if qiskit_compat:
        processed = apply_qiskit_compatibility(
            processed,
            literal_nodes or (),
            literal_nodes_with_consumers or (),
        )
    return cast_to_program(SortImportsTransformer().visit(processed))

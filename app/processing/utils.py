"""
Utils used within :mod:`app.processing`.
"""

import re

from openqasm3.ast import (
    Program,
    QASMNode,
)

REMOVE_INDENT = re.compile(r"\n +", re.MULTILINE)


def normalize_qasm_string(program: str) -> str:
    """
    Normalize QASM-string.
    """
    return REMOVE_INDENT.sub("\n", program).strip()


def cast_to_program(node: QASMNode | None) -> Program:
    """
    Cast to Program or raise error.
    """
    if not isinstance(node, Program):
        msg = f"Tried to cast {type(node)} to Program."
        raise TypeError(msg)
    return node

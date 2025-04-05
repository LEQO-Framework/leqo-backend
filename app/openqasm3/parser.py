"""
Extended parsing of abstract syntax trees with support for `OPENQASM 2.x`.
"""

from openqasm3.ast import Program
from openqasm3.parser import parse


def leqo_parse(qasm: str) -> Program:
    """
    Parses an openqasm2 or openqasm3 string into an ast (:class:`~openqasm3.ast.Program`)

    :param qasm: The qasm string to parse
    :return: The parse ast
    """

    # ToDo: Check for openqasm2 and wire converter
    return parse(qasm)

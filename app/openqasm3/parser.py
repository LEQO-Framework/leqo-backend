from openqasm3.ast import Program

from app.converter import parse_to_openqasm3


def leqo_parse(qasm: str) -> Program:
    """Parse an openqasm2 or openqasm3 string into an ast (:class:`~openqasm3.ast.Program`).

    :param qasm: The qasm string to parse
    :return: The parse ast
    """
    return parse_to_openqasm3(qasm)

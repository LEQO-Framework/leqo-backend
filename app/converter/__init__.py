from openqasm3.ast import Program

from app.converter.qasm_converter import CustomOpenqamsLib, QASMConverter


def parse_to_openqasm3(
    code: str,
    custom_libs: list[CustomOpenqamsLib] | None = None,
) -> Program:
    """Parse an OpenQASM 2.x/3.x string to an equivalent OpenQASM 3.1 AST.

    :param code: The code-string to be parsed and converted if required.
    :param custom_libs: An optional list of custom provided libraries. "qelib1.inc" is builtin.
    :return: The converted/parsed OpenQASM 3.1 AST.
    """
    custom_libs = [] if custom_libs is None else custom_libs
    return QASMConverter(custom_libs).parse_to_qasm3(code)

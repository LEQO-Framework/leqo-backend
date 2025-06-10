from openqasm3.ast import Program

from app.converter.qasm_converter import CustomOpenqasmLib, QASMConverter


def parse_to_openqasm3(
    code: str,
    custom_libs: list[CustomOpenqasmLib] | None = None,
) -> Program:
    """Parse an Openqasm2.x/3.x string to an equivalent Openqasm3.1 AST.

    :param code: The code-string to be parsed and converted if required.
    :param custom_libs: An optional list of custom provided libraries. "qelib1.inc" is builtin.
    :return: The converted/parsed Openqasm 3 AST.
    """
    custom_libs = [] if custom_libs is None else custom_libs
    return QASMConverter(custom_libs).parse_to_qasm3(code)

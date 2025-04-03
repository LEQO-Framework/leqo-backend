from openqasm3.ast import Program

from app.converter.qasm_converter import CustomOpenqamsLib, QASMConverter


def parse_to_openqasm3(
    code: str,
    custom_libs: list[CustomOpenqamsLib] | None = None,
) -> Program:
    """Parse an Openqasm2.x/3.x string to an equivalent Openqasm3.1 AST.

    :param code: The Openqasm2.x code to be converted.
    :param custom_libs: A list of custom provided libraries. "qelib1.inc" is builtin.
    :return: The converted Openqasm3.1 string.
    """
    custom_libs = [] if custom_libs is None else custom_libs
    return QASMConverter(custom_libs).parse_to_qasm3(code)

from app.converter.qasm_converter import CustomOpenqamsLib, QASMConverter


def openqasm2_to_openqasm3(code: str, custom_libs: list[CustomOpenqamsLib]) -> str:
    """Convert an Openqasm2.x string to an equivalent Openqasm3.1 string.

    :param code: The Openqasm2.x code to be converted.
    :param custom_libs: A list of custom provided libraries. "qelib1.inc" is builtin.
    :return: The converted Openqasm3.1 string.
    """
    return QASMConverter(custom_libs).qasm2_to_qasm3(code)

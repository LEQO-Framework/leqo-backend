from app.converter.qasm_converter import CustomOpenqams2Lib, QASMConverter


def openqams2_to_openqasm3(code: str, custom_libs: list[CustomOpenqams2Lib]) -> str:
    return QASMConverter(custom_libs).qasm2_to_qasm3(code)

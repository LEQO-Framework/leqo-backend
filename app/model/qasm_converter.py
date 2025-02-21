import os

from openqasm3 import parser, printer


# Custom exception for errors during QASM conversion
class QASMConversionError(Exception):
    pass


def change_qasm2_line_to_qasm3(line: str) -> str:
    """
    Converts a single line of QASM 2.x code into a QASM 3.0 compatible format.

    This method processes one line of QASM 2.x code, removing or modifying elements that
    are not compatible with QASM 3.0. It performs the following transformations:
    - Removes the 'OPENQASM 2.x' header.
    - Ignores the 'include "qelib1.inc";' statement.
    - Converts 'opaque' statements into comments by prepending "// ".

    If an unsupported QASM version or library is encountered, a QASMConversionError is raised.

    Arguments:
        line (str): A single line of QASM 2.x code to be converted.

    Returns:
        str: A line of code in QASM 3.0 format (or an empty string for unsupported lines).

    Raises:
        QASMConversionError: If the line contains an unsupported QASM version or library.
    """

    # Remove leading whitespace from the line
    line = line.lstrip()

    if line.startswith("OPENQASM"):
        if line.startswith("OPENQASM 2"):
            return ""
        raise QASMConversionError(
            "Unsupported QASM version. Only 'OPENQASM 2.x' is allowed."
        )

    if line.startswith("include"):
        if line == 'include "qelib1.inc";':
            return ""
        raise QASMConversionError(
            "Unsupported library included. Only 'qelib1.inc' is allowed."
        )

    if line.startswith("opaque"):
        # As opaque is ignored by OpenQASM 3, add it as a comment
        return "// " + line + "\n"

    return line + "\n"


def convert_qasm2_to_qasm3(qasm2_code: str) -> str:
    """
    Converts an entire QASM 2.x program into a QASM 3.0 compatible program.

    This method processes a full QASM 2.x program, transforming it into a valid QASM 3.0 format.
    The conversion process includes the following steps:
    - The 'OPENQASM 2.x' header is replaced with 'OPENQASM 3.0' and the inclusion of standard gates.
    - The 'include "qelib1.inc";' statement is ignored.
    - 'opaque' statements are converted into comments.
    - Additional gate definitions from 'qelib1.inc' are appended.

    Arguments:
        qasm2_code (str): A string containing QASM 2.x code to be converted.

    Returns:
        str: A string containing the converted QASM 3.0 code, formatted according to QASM 3.0 standards.

    Raises:
        QASMConversionError: If any line contains an unsupported QASM version or library.
    """

    # Start the QASM 3 code with the required header and include statement for standard gates
    qasm3_code = """OPENQASM 3.0;
    include 'stdgates.inc';
    """

    # Add the gates from qelib1.inc not present in the stdgates.inc file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    with open(
        os.path.join(current_dir, "qasm_lib/qasm3_qelib1.qasm"),
        encoding="utf-8",
    ) as gate_defs:
        for line in gate_defs:
            qasm3_code += line

    for line in qasm2_code.splitlines():
        transformed_line = change_qasm2_line_to_qasm3(line)
        qasm3_code += transformed_line

    # Parse the QASM 3 code into an Abstract Syntax Tree (AST)
    program_ast = parser.parse(qasm3_code)

    # Convert the AST back into a formatted QASM string
    return printer.dumps(program_ast)

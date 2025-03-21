import os
import re

from openqasm3 import parser, printer

# regex comment pattern
line_comment_pattern = re.compile(r"//.*")
block_comment_pattern = re.compile(r"/\*.*?\*/", re.DOTALL)

# regex gate pattern
gate_pattern = re.compile(
    r"gate\s+(\w+)\s*(\([^)]*\))?\s*([\w,\s]+)\s*\{([\s\S]*?)\}\s*", re.DOTALL
)
letter_number_pattern = re.compile(r"^[a-zA-Z0-9]+")

# regex OpenQASM pattern
qasm_version_pattern = re.compile(r"^OPENQASM\s+(\d+(\.\d+)?)\s*;")
qelib1_pattern = re.compile(r'include\s+"qelib1\.inc"\s*;')
opaque_statement_pattern = re.compile(r"^opaque\s")


# Custom exception for errors during QASM conversion
class QASMConversionError(Exception):
    """
    Custom exception raised for errors occurring during QASM conversion.
    """


def remove_comments(content: str) -> str:
    """
    Removes both single-line (``//``) and multi-line (``/* */``) comments from the given QASM content.

    :param content: The QASM code content as a string.

    :returns: The QASM content with comments removed.
    """
    content = line_comment_pattern.sub("", content)  # Remove single-line comments
    return block_comment_pattern.sub("", content)


class QASMConverter:
    """
    Converts QASM 2.x code to QASM 3.0, handling unsupported gates and libraries.
    """

    def __init__(self, libs_extens_files: list[str] | None = None) -> None:
        """
        Initializes the QASMConverter with optional external QASM files for unsupported gates.

        :param libs_extens_files: List of QASM files containing additional gate definitions.
        """
        if libs_extens_files is None:
            libs_extens_files = ["qasm3_qelib1.qasm"]
        self.qasm2_unsupported_libs = libs_extens_files
        self.qasm2_unsupported_gates = self.__load_unique_gates_from_files(
            libs_extens_files
        )

    def qasm2_to_qasm3(self, qasm2_code: str) -> str:
        """
        Converts an entire QASM 2.x program into a QASM 3.0 compatible program.

        Warning: All comments present in the given QASM code will be removed!!!

        This method processes a full QASM 2.x program, transforming it into a valid QASM 3.0 format.
        The conversion process includes the following steps:

        - The 'OPENQASM 2.x' header is replaced with 'OPENQASM 3.0' and the inclusion of standard gates.
        - The 'include "qelib1.inc";' statement is ignored.
        - 'opaque' statements are converted into comments.
        - Additional gate definitions from 'qelib1.inc' are appended.

        :param qasm2_code: A string containing QASM 2.x code to be converted.

        :return: A string containing the converted QASM 3.0 code, formatted according to QASM 3.0 standards.

        :raises QASMConversionError: If any line contains an unsupported QASM version or library.
        """

        # Remove single- and multi-line comments
        qasm2_code = remove_comments(qasm2_code)

        # Start the QASM 3 code with the required header and include statement for standard gates
        qasm3_code = """OPENQASM 3.0;
        include 'stdgates.inc';
        """

        for line in qasm2_code.splitlines():
            transformed_line = self.__change_qasm2_line_to_qasm3(line)
            qasm3_code += transformed_line

        # Parse the QASM 3 code into an Abstract Syntax Tree (AST)
        program_ast = parser.parse(qasm3_code)

        # Convert the AST back into a formatted QASM string
        qasm3_code = printer.dumps(program_ast)

        # Create unsupported helper gates
        snippet = self.create_unsupported_gates_snippet(qasm3_code)

        result = ""
        added_snippet = False
        for line in qasm3_code.splitlines():
            if not added_snippet and (
                not line.startswith("OPENQASM") and not line.startswith("include")
            ):
                result += snippet
                added_snippet = True

            result += line + "\n"

        return result

    def is_unsupported_gate(self, gate: str) -> bool:
        """
        Checks if a given gate is unsupported in QASM 3.0 and requires a helper definition.

        :param gate: The name of the gate to check.

        :return: True if the gate is unsupported, False otherwise.
        """
        return gate in self.qasm2_unsupported_gates

    def create_unsupported_gates_snippet(self, qasm3_code: str) -> str:
        """
        Generates QASM 3.0 helper gate definitions for unsupported QASM 2.x gates found in the converted code.

        :param qasm3_code: The converted QASM 3.0 code.

        :return: A string that may contain helper gate definitions
        """
        snippets = """\n// Generated helper gates for unsupported QASM 2.x gates ////////\n\n"""
        added_gates = set()
        unsupported_gate_detected = False
        for rawline in qasm3_code.splitlines():
            line = rawline.lstrip()
            match_gates = letter_number_pattern.search(line)
            if (
                match_gates
                and self.is_unsupported_gate(match_gates.group(0))
                and (match_gates not in added_gates)
            ):
                unsupported_gate_detected = True
                gate = match_gates.group(0)
                details = self.qasm2_unsupported_gates.get(gate)

                if details is None:
                    raise QASMConversionError(
                        f"Couldn't process unsupported QASM 2.x gate '{gate}'"
                    )

                added_gates.add(gate)

                qasm3_code = f"""// Helper gate for {gate} \ngate {gate}{details[0]} {details[1]} \n{{\n    {details[2]}\n}}\n\n"""

                snippets += qasm3_code

        if unsupported_gate_detected:
            snippets += """\n""" + ("/" * 65) + """\n\n"""
            return snippets
        return """"""

    @staticmethod
    def __load_unique_gates_from_files(file_list: list[str]) -> dict[str, list[str]]:
        """
        Reads QASM files specified during initialization and extracts unique gate definitions.

        :param file_list: A list of filenames containing QASM gate definitions.

        :return: A dictionary where the gate name maps to its parameters, qubits, body, and source file.
        """
        unique_gates = set()
        gate_details: dict[str, list[str]] = {}

        for filename in file_list:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(current_dir, "qasm_lib/" + filename)
            with open(
                path,
                encoding="utf-8",
            ) as f:
                content = f.read()

                # Remove comments before processing
                content = remove_comments(content)

                for match in gate_pattern.finditer(content):
                    name = match.group(1)
                    parameters = match.group(2) if match.group(2) is not None else ""
                    qubits = match.group(3).strip()
                    body = match.group(4).strip()

                    # Normalize whitespace to avoid formatting issues
                    body = re.sub(r"\s+", " ", body)

                    # Create a tuple representing the gate (hashable)
                    gate_tuple = (name, parameters, qubits, body, filename)
                    if gate_tuple not in unique_gates:
                        unique_gates.add(gate_tuple)
                        # Store the dictionary representation
                        gate_details.setdefault(
                            name, [parameters, qubits, body, filename]
                        )

        return gate_details

    @staticmethod
    def __change_qasm2_line_to_qasm3(line: str) -> str:
        """
        Converts a single line of QASM 2.x code into a QASM 3.0 compatible format.

        This method processes one line of QASM 2.x code, removing or modifying elements that
        are not compatible with QASM 3.0. It performs the following transformations:

        - Removes the 'OPENQASM 2.x' header.
        - Ignores the 'include "qelib1.inc";' statement.
        - Converts 'opaque' statements into comments by prepending "// ".

        If an unsupported QASM version or library is encountered, a QASMConversionError is raised.

        :param line: A single line of QASM 2.x code to be converted.

        :return: A line of code in QASM 3.0 format (or an empty string for unsupported lines).

        :raises QASMConversionError: If the line contains an unsupported QASM version or library.
        """

        # Remove leading whitespace from the line
        line = line.lstrip()

        # Split the line into individual commands using `;`, keeping `;`
        commands = [cmd.strip() + ";" for cmd in line.split(";") if cmd.strip()]

        processed_commands = []

        for cmd in commands:
            # Check for a valid OPENQASM version
            match = qasm_version_pattern.match(cmd)
            if match:
                if match.group(1).startswith("2"):
                    continue  # Remove the line (replace with nothing)
                raise QASMConversionError(
                    "Unsupported QASM version. Only 'OPENQASM 2.x' is allowed."
                )

            # Check for the allowed `include` statement
            if qelib1_pattern.fullmatch(cmd):
                continue  # Remove this command

            if cmd.startswith("include"):
                raise QASMConversionError(
                    "Unsupported library included. Only 'qelib1.inc' is allowed."
                )

            # Convert `opaque` statements into comments
            if opaque_statement_pattern.match(cmd):
                processed_commands.append("// " + cmd)
                continue

            # Keep all other valid commands
            processed_commands.append(cmd)

        return "".join(processed_commands) + "\n"

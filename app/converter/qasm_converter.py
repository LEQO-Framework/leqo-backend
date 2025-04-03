import re
from pathlib import Path

from openqasm3.ast import Include, Program, QASMNode, QuantumGate, QuantumGateDefinition
from openqasm3.parser import parse
from openqasm3.printer import dumps

from app.openqasm3.visitor import LeqoTransformer

OPAQUE_STATEMENT_PATTERN = re.compile(r"opaque\s\([^;]+\).+;", re.MULTILINE)
LIB_REPLACEMENTS = {"qelib1": "stdgates.inc"}


class CustomOpenqams2Lib:
    name: str
    content: str
    gates: list[QuantumGateDefinition]

    def __init__(self, name: str, content: str) -> None:
        self.name = name
        self.content = content
        self.gates = []
        for statement in parse(content).statements:
            if isinstance(statement, QuantumGateDefinition):
                self.gates.append(statement)


# Custom exception for errors during QASM conversion
class QASMConversionError(Exception):
    """Custom exception raised for errors occurring during QASM conversion."""


class ApplyCustomGates(LeqoTransformer[None]):
    libs: dict[str, CustomOpenqams2Lib]
    lib_replacements: dict[str, str]
    gates: dict[str, QuantumGateDefinition]
    require_gates: set[str]
    includes: dict[str, Include]

    def __init__(
        self,
        custom_libs: dict[str, CustomOpenqams2Lib],
        lib_replacements: dict[str, str],
    ) -> None:
        super().__init__()
        self.libs = custom_libs
        self.lib_replacements = lib_replacements

        self.gates = {}
        for lib in self.libs.values():
            for gate in lib.gates:
                self.gates[gate.name.name] = gate
        self.require_gates = set()
        self.includes = {}

    def visit_Include(self, node: Include) -> None:
        name = node.filename
        if name in self.lib_replacements:
            node.filename = self.lib_replacements[name]
            self.includes[name] = node
        elif name not in self.libs:
            self.includes[name] = node

    def visit_QuantumGate(self, node: QuantumGate) -> QASMNode:
        name = node.name.name
        if name in self.gates:
            self.require_gates.add(name)
        return self.generic_visit(node)

    def visit_Program(self, node: Program) -> QASMNode:
        self.generic_visit(node)
        node.statements = (
            sorted(self.includes.values(), key=lambda imp: imp.filename)
            + [self.gates[gd] for gd in self.require_gates]
            + node.statements
        )
        return node


class QASMConverter:
    """Converts QASM 2.x code to QASM 3.0, handling unsupported gates and libraries."""

    custom_libs: dict[str, CustomOpenqams2Lib]

    def add_custom_gate_lib(self, lib: CustomOpenqams2Lib) -> None:
        self.custom_libs[lib.name] = lib

    def __init__(self, custom_libs: list[CustomOpenqams2Lib] | None = None) -> None:
        """Initialize the QASMConverter with optional external QASM files for unsupported gates.

        :param libs_extens_files: List of QASM files containing additional gate definitions.
        """
        self.custom_libs = {}
        if custom_libs is not None:
            for lib in custom_libs:
                self.add_custom_gate_lib(lib)
        with (
            Path(__file__).absolute().parent / "qasm_lib" / "qasm3_qelib1.qasm"
        ).open() as f:
            self.add_custom_gate_lib(CustomOpenqams2Lib("qelib1.inc", f.read()))

    def qasm2_to_qasm3(self, qasm2_code: str) -> str:
        """Convert an entire QASM 2.x program into a QASM 3.0 compatible program.

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
        opaque = OPAQUE_STATEMENT_PATTERN.findall(qasm2_code)
        if opaque is not None:
            msg = f"Unsupported opaque definition {opaque} could not be ported to openqasm3."
            raise QASMConversionError(msg)

        ast = parse(qasm2_code)
        ast.version = "3.1"

        if not ast.version.startswith("2"):
            msg = f"Unsupported openqasm version {ast.version} could not be ported to openqasm3."
            raise QASMConversionError(msg)

        ast = ApplyCustomGates(self.custom_libs, LIB_REPLACEMENTS).visit(ast)

        return dumps(ast)

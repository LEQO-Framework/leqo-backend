"""Convert **OpenQASM 2.x** code into **OpenQASM TARGET_QASM_VERSION** AST.

The conversion process includes handling unsupported gates, transforming obsolete syntax
and integrating necessary gate definitions from external libraries.

.. warning::

   **Comment Removal:** All single-line (`//`)
   and multi-line (`/* */`) comments will be **permanently removed** during the conversion process.
   Ensure that important notes or documentation within the QASM code are backed up separately.

.. warning::

   **Can't handle ``opaque``:** This converter will raise an error if it encounters an ``opaque``,
   as this is unsupported in Openqasm3.

.. warning::

   **Custom gates only for Openqasm2** CustomOpenqamsLib's have no effect if the code is already qasm3.

Key Features
------------

- **Automated QASM Conversion**: Seamlessly converts QASM 2.x code into valid QASM TARGET_QASM_VERSION format.
- **Unsupported Gate Management**: Detects and provides definitions for gates specified in "qelib1.inc".
- **Library Integration**: Incorporates additional QASM gate definitions from provided strings.
"""

import re
from pathlib import Path

from openqasm3.ast import Include, Program, QASMNode, QuantumGate, QuantumGateDefinition
from openqasm3.parser import parse

from app.openqasm3.visitor import LeqoTransformer
from app.processing.utils import cast_to_program

OPAQUE_STATEMENT_PATTERN = re.compile(
    r"opaque\s+[a-zA-Z0-9_\-]+\s*\([^;]+\)[^;]+;",
    re.MULTILINE,
)
LIB_REPLACEMENTS = {"qelib1.inc": "stdgates.inc"}
TARGET_QASM_VERSION = "3.1"


class CustomOpenqamsLib:
    """Openqasm3 library for providing gates used in Openqasm2.x."""

    name: str
    content: str
    gates: list[QuantumGateDefinition]

    def __init__(self, name: str, content: str) -> None:
        """Construct CustomOpenqamsLib.

        :param name: The name of the module.
        :param content: The Openqasm3 custom gate definitions as a string.
        """
        self.name = name
        self.content = content
        self.gates = []
        for statement in parse(content).statements:
            if isinstance(statement, QuantumGateDefinition):
                self.gates.append(statement)


class QASMConversionError(Exception):
    """Custom exception raised for errors occurring during QASM conversion."""


class ApplyCustomGates(LeqoTransformer[None]):
    """Visitor to replace gates provided by custom libraries."""

    libs: dict[str, CustomOpenqamsLib]
    lib_replacements: dict[str, str]
    gates: dict[str, QuantumGateDefinition]
    require_gates: set[str]
    includes: dict[str, Include]

    def __init__(
        self,
        custom_libs: dict[str, CustomOpenqamsLib],
        lib_replacements: dict[str, str],
    ) -> None:
        """Construct ApplyCustomGates.

        :param custom_libs: Dictionary of custom libs to use.
        :param lib_replacements: lib-names to be replaced inside include statements (e.g. qelib1.inc -> stdgates.inc)
        """
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
        """Remove and store required includes, possible modify via lib_replacements."""
        name = node.filename
        if name in self.lib_replacements:
            node.filename = self.lib_replacements[name]
            self.includes[name] = node
        elif name not in self.libs:
            self.includes[name] = node

    def visit_QuantumGate(self, node: QuantumGate) -> QASMNode:
        """Search for usages of custom declared gates."""
        name = node.name.name
        if name in self.gates:
            self.require_gates.add(name)
        return self.generic_visit(node)

    def visit_Program(self, node: Program) -> QASMNode:
        """Apply the visitor.

        1. Remove imports + gather info
        2. Add required (possible imports) back
        3. Insert definitions of custom gates
        """
        self.generic_visit(node)
        node.statements = (
            sorted(self.includes.values(), key=lambda imp: imp.filename)
            + [self.gates[gd] for gd in sorted(self.require_gates)]
            + node.statements
        )
        return node


class QASMConverter:
    """Converts QASM 2.x code to QASM TARGET_QASM_VERSION."""

    custom_libs: dict[str, CustomOpenqamsLib]

    def add_custom_gate_lib(self, lib: CustomOpenqamsLib) -> None:
        """Append custom lib to internal data."""
        self.custom_libs[lib.name] = lib

    def __init__(self, custom_libs: list[CustomOpenqamsLib] | None = None) -> None:
        """Initialize the QASMConverter with optional external QASM files for unsupported gates.

        :param custom_libs: List of CustomOpenqamsLib's containing additional gate definitions.
        """
        self.custom_libs = {}
        if custom_libs is not None:
            for lib in custom_libs:
                self.add_custom_gate_lib(lib)
        with (
            Path(__file__).absolute().parent / "qasm_lib" / "qasm3_qelib1.qasm"
        ).open() as f:
            self.add_custom_gate_lib(CustomOpenqamsLib("qelib1.inc", f.read()))

    def parse_to_qasm3(self, qasm2_code: str) -> Program:
        """Convert an entire QASM 2.x program into a QASM TARGET_QASM_VERSION compatible program.

        Warning: All comments present in the given QASM code will be removed!!!

        This method processes a full QASM 2.x program, transforming it into valid QASM TARGET_QASM_VERSION.
        The conversion process includes the following steps:

        1. Check for opaque, raise error if there
        2. Parse into AST
        3. If version 3.x, return AST
        4. If version not 3.x or 2.x, raise error
        5. Set version TARGET_QASM_VERSION
        6. Include gates from custom libs, replace/remove obsolete imports

        :param qasm2_code: A string containing QASM 2.x code to be converted.

        :return: AST in Openqasm TARGET_QASM_VERSION format.

        :raises QASMConversionError: If any line contains an unsupported QASM version or library or opaque was used.
        """
        opaque = OPAQUE_STATEMENT_PATTERN.findall(qasm2_code)
        if len(opaque) != 0:
            msg = f"Unsupported opaque definition {opaque} could not be ported to openqasm3."
            raise QASMConversionError(msg)

        result = parse(qasm2_code)

        if result.version is None:
            msg = "No Openqasm version specified."
            raise QASMConversionError(msg)
        if result.version.startswith("3"):
            result.version = TARGET_QASM_VERSION
            return result
        if not result.version.startswith("2"):
            msg = f"Unsupported openqasm version {result.version} could not be ported to openqasm3."
            raise QASMConversionError(msg)

        result.version = TARGET_QASM_VERSION

        return cast_to_program(
            ApplyCustomGates(self.custom_libs, LIB_REPLACEMENTS).visit(result),
        )

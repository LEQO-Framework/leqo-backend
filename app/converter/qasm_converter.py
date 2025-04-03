"""Convert **OpenQASM 2.x** code into **OpenQASM 3.1**.

The conversion process includes handling unsupported gates, transforming obsolete syntax
and integrating necessary gate definitions from external libraries.

.. warning::

   **Comment Removal:** All single-line (`//`)
   and multi-line (`/* */`) comments will be **permanently removed** during the conversion process.
   Ensure that important notes or documentation within the QASM code are backed up separately.

.. warning::

   **Can't handle ``opaque``:** This converter will raise an error if it encounters an ``opaque``,
   as this is unsupported in Openqasm3.

Key Features
------------

- **Automated QASM Conversion**: Seamlessly converts QASM 2.x code into valid QASM 3.0 format.
- **Unsupported Gate Management**: Detects and provides definitions for gates specified in "qelib1.inc".
- **Library Integration**: Incorporates additional QASM gate definitions from provided strings.
"""

import re
from pathlib import Path

from openqasm3.ast import Include, Program, QASMNode, QuantumGate, QuantumGateDefinition
from openqasm3.parser import parse
from openqasm3.printer import dumps

from app.openqasm3.visitor import LeqoTransformer

OPAQUE_STATEMENT_PATTERN = re.compile(
    r"opaque\s+[a-zA-Z0-9_\-]+\s*\([^;]+\)[^;]+;",
    re.MULTILINE,
)
LIB_REPLACEMENTS = {"qelib1.inc": "stdgates.inc"}


class CustomOpenqamsLib:
    """Openqasm3 library for providing gates used in Openqasm2.x."""

    name: str
    content: str
    gates: list[QuantumGateDefinition]

    def __init__(self, name: str, content: str) -> None:
        """Construct CustomOpenqamsLib.

        :param name: The name of the module.
        :param content: The code of the module as string.
        """
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
        :param lib_replacements: Replace lib-names to new names (qelib1.inc -> stdgates.inc)
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
    """Converts QASM 2.x code to QASM 3.0."""

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

    def qasm2_to_qasm3(self, qasm2_code: str) -> str:
        """Convert an entire QASM 2.x program into a QASM 3.1 compatible program.

        Warning: All comments present in the given QASM code will be removed!!!

        This method processes a full QASM 2.x program, transforming it into valid QASM 3.1.
        The conversion process includes the following steps:

        1. Check for opaque, raise error if there
        2. Parse into AST
        3. Check for version, raise error if not Openqasm2.x
        4. Set version 3.1
        5. Include gates from custom libs, replace/remove obsolete imports
        6. Dump result

        :param qasm2_code: A string containing QASM 2.x code to be converted.

        :return: A string containing the converted QASM 3.0 code, formatted according to QASM 3.0 standards.

        :raises QASMConversionError: If any line contains an unsupported QASM version or library or opaque was used.
        """
        opaque = OPAQUE_STATEMENT_PATTERN.findall(qasm2_code)
        if len(opaque) != 0:
            msg = f"Unsupported opaque definition {opaque} could not be ported to openqasm3."
            raise QASMConversionError(msg)

        ast = parse(qasm2_code)

        if ast.version is None:
            msg = "No Openqasm version specified."
            raise QASMConversionError(msg)
        if not ast.version.startswith("2"):
            msg = f"Unsupported openqasm version {ast.version} could not be ported to openqasm3."
            raise QASMConversionError(msg)

        ast.version = "3.1"

        ast = ApplyCustomGates(self.custom_libs, LIB_REPLACEMENTS).visit(ast)

        return dumps(ast)

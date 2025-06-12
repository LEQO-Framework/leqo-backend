"""Convert **OpenQASM 2.x/3.x** code into an **OpenQASM 3.x** AST.

The conversion process includes handling unsupported gates, transforming obsolete syntax
and integrating necessary gate definitions from external libraries.

.. warning::

   **Comment Removal:** All single-line (`//`)
   and multi-line (`/* */`) comments will be **permanently removed** during the conversion process.
   Ensure that important notes or documentation within the QASM code are backed up separately.

.. warning::

   **Can't handle ``opaque``:** This converter will raise an error if it encounters an ``opaque``,
   as this is unsupported in OpenQASM 3.x.

.. warning::

   **Custom gates only for OpenQASM 2.x** CustomOpenqasmLib's have no effect if the code is already OpenQASM 3.x.

..note::
    **Used OpenQASM version: 3.1** If the code is OpenQASM 2.x, it will be converted
    to OpenQASM 3.1. If it is already 3.x, the version is not changed.


Key Features
------------

- **Automated QASM Conversion**: Seamlessly converts QASM 2.x code into valid QASM 3.1 format.
- **Unsupported Gate Management**: Detects and provides definitions for gates specified in "qelib1.inc".
- **Library Integration**: Incorporates additional QASM gate definitions from provided strings.
"""

import re
from pathlib import Path

from openqasm3.ast import Include, Program, QASMNode, QuantumGate, QuantumGateDefinition
from openqasm3.parser import parse

from app.exceptions import ServerError
from app.openqasm3.visitor import LeqoTransformer
from app.processing.utils import cast_to_program

OPAQUE_STATEMENT_PATTERN = re.compile(
    r"opaque\s+[a-zA-Z0-9_\-]+\s*\([^;]+\)[^;]+;",
    re.MULTILINE,
)
UNCOMPUTE_BLOCK_PATTERN = re.compile(
    r"^\s*//\s*@leqo\.uncompute\s+start\s*\n(.*)\n\s*//\s*@leqo.uncompute\s+end\s*$",
    re.MULTILINE | re.DOTALL,
)
ANNOTATION_WITH_ALIAS_PATTERN = re.compile(
    r"^\s*//\s*(@leqo.*)$\n\s*//\s*(let\s.*;)\s*$",
    re.MULTILINE,
)
ANNOTATION_PATTERN = re.compile(r"^\s*//\s*(@.+)$", re.MULTILINE)
LIB_REPLACEMENTS = {"qelib1.inc": "stdgates.inc"}
# NOTE: if this version is updated, the docs need to be updated also
TARGET_QASM_VERSION = "3.1"


class CustomOpenqasmLib:
    """OpenQASM3 library for providing gates used in OpenQASM2.x."""

    name: str
    content: str
    gates: list[QuantumGateDefinition]

    def __init__(self, name: str, content: str) -> None:
        """Construct CustomOpenqasmLib.

        :param name: The name of the module.
        :param content: The custom gate definitions in OpenQASM 3.x as string.
        """
        self.name = name
        self.content = content
        self.gates = []
        for statement in parse(content).statements:
            if isinstance(statement, QuantumGateDefinition):
                self.gates.append(statement)


class QASMConversionError(ServerError):
    """Custom exception raised for errors occurring during QASM conversion."""


class ApplyCustomGates(LeqoTransformer[None]):
    """Visitor to replace gates provided by custom libraries."""

    libs: dict[str, CustomOpenqasmLib]
    lib_replacements: dict[str, str]
    gates: dict[str, QuantumGateDefinition]
    require_gates: set[str]
    includes: dict[str, Include]

    def __init__(
        self,
        custom_libs: dict[str, CustomOpenqasmLib],
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
    """Convert QASM 2.x code to QASM 3.1 AST or return parsed OpenQASM 3.x. directly"""

    custom_libs: dict[str, CustomOpenqasmLib]
    __node_id: str | None

    def add_custom_gate_lib(self, lib: CustomOpenqasmLib) -> None:
        """Append custom lib to internal data."""
        self.custom_libs[lib.name] = lib

    def __init__(
        self,
        custom_libs: list[CustomOpenqasmLib] | None = None,
        node_id: str | None = None,
    ) -> None:
        """Initialize the QASMConverter with optional external QASM files for unsupported gates.

        :param custom_libs: List of CustomOpenqasmLib's containing additional gate definitions.
        """
        self.__node_id = node_id
        self.custom_libs = {}
        if custom_libs is not None:
            for lib in custom_libs:
                self.add_custom_gate_lib(lib)
        with (
            Path(__file__).absolute().parent
            / "qasm_lib_for_converter"
            / "qasm3_qelib1.qasm"
        ).open() as f:
            self.add_custom_gate_lib(CustomOpenqasmLib("qelib1.inc", f.read()))

    def parse_to_qasm3(self, qasm2_code: str) -> Program:
        """Convert entire QASM 2.x code to QASM 3.1 AST or return parsed OpenQASM 3.x. directly

        Warning: All comments present in the given QASM code will be removed!!!

        This method processes a QASM 2.x/3.x program, transforming it into valid QASM 3.x.
        The conversion process includes the following steps:

        1. Check for opaque, raise error if there
        2. Parse into AST
        3. If version 3.x, return AST
        4. If neither version 3.x or 2.x, raise error
        5. Set version 3.1
        6. Include gates from custom libs, replace/remove obsolete imports

        :param qasm2_code: A string containing QASM 2.x/3.x code to be converted.

        :return: AST in OpenQASM 3.x format.

        :raises QASMConversionError: If any line contains an unsupported QASM version or library or opaque was used.
        """
        opaque = OPAQUE_STATEMENT_PATTERN.findall(qasm2_code)
        if len(opaque) != 0:
            msg = f"Unsupported opaque definition {opaque} could not be ported to OpenQASM 3."
            raise QASMConversionError(msg, node=self.__node_id)

        qasm2_code = UNCOMPUTE_BLOCK_PATTERN.sub(
            r"@leqo.uncompute\nif(false) {\n\1\n}",
            qasm2_code,
        )
        qasm2_code = ANNOTATION_WITH_ALIAS_PATTERN.sub(r"\1\n\2", qasm2_code)
        qasm2_code = ANNOTATION_PATTERN.sub(r"\1", qasm2_code)

        result = parse(qasm2_code)

        if result.version is None:
            msg = "No OpenQASM version specified."
            raise QASMConversionError(msg)
        if result.version.startswith("3"):
            return result
        if not result.version.startswith("2"):
            msg = f"Unsupported OpenQASM version {result.version} could not be ported to OpenQASM 3.1."
            raise QASMConversionError(msg)

        result.version = TARGET_QASM_VERSION

        return cast_to_program(
            ApplyCustomGates(self.custom_libs, LIB_REPLACEMENTS).visit(result),
        )


def parse_to_openqasm3(
    code: str,
    custom_libs: list[CustomOpenqasmLib] | None = None,
    node_id: str | None = None,
) -> Program:
    """Parse an Openqasm2.x/3.x string to an equivalent Openqasm3.1 AST.

    :param code: The code-string to be parsed and converted if required.
    :param custom_libs: An optional list of custom provided libraries. "qelib1.inc" is builtin.
    :return: The converted/parsed Openqasm 3 AST.
    """
    custom_libs = [] if custom_libs is None else custom_libs
    return QASMConverter(custom_libs, node_id).parse_to_qasm3(code)

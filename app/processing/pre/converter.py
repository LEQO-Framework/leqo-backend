"""Convert **OpenQASM 2.x/3.x** code into an **OpenQASM 3.1** AST.

The conversion process includes handling unsupported gates, transforming obsolete syntax
and integrating necessary gate definitions from external libraries.

.. warning::

   **Comment Removal:** All single-line (`//`)
   and multi-line (`/* */`) comments will be **permanently removed** during the conversion process.
   Ensure that important notes or documentation within the OpenQASM code are backed up separately.

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

- **Automated OpenQASM Conversion**: Seamlessly converts OpenQASM 2.x code into valid OpenQASM 3.1 format.
- **Unsupported Gate Management**: Detects and provides definitions for gates specified in "qelib1.inc".
- **Library Integration**: Incorporates additional OpenQASM gate definitions from provided strings.
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
    """Encapsulates an OpenQASM 3.x-compatible gate library for custom gate resolution.

    Used to provide gate definitions (e.g., from qelib1.inc) that can be injected into
    converted OpenQASM 2.x code. Only gate definitions (`QuantumGateDefinition`) are retained."""

    name: str
    content: str
    gates: list[QuantumGateDefinition]

    def __init__(self, name: str, content: str) -> None:
        """Initialize the custom gate library

        :param name: The name of the module.
        :param content: The custom gate definitions in OpenQASM 3.x as string.
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
    """AST visitor that injects custom gate definitions and filters include statements.

    This visitor:
    1. Tracks which gate definitions from the custom libs are actually used.
    2. Replaces outdated `include` directives (e.g., `qelib1.inc`) if provided as custom libs.
    3. Inserts required gate definitions and imports into the AST.
    """

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
        """Initialize the visitor with libraries and replacement rules.

        :param custom_libs: Dictionary of custom libraries with gate definitions.
        :param lib_replacements: Mapping of include lib-names to replacements (e.g. qelib1.inc -> stdgates.inc)
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

    def visit_QuantumGate(self, node: QuantumGate) -> QASMNode:
        """Search for usages of custom declared gates.

        :param node: Quantum gate AST node.
        """
        name = node.name.name
        if name in self.gates:
            self.require_gates.add(name)
        return self.generic_visit(node)

    def visit_Include(self, node: Include) -> None:
        """Remove and store required includes, possible modify via lib_replacements.

        :param node: The include node from the OpenQASM AST.
        """
        name = node.filename
        if name in self.lib_replacements:
            node.filename = self.lib_replacements[name]
            self.includes[name] = node
        elif name not in self.libs:
            self.includes[name] = node

    def visit_Program(self, node: Program) -> QASMNode:
        """Apply the visitor.

        1. Remove imports + gather info
        2. Add required (possible imports) back
        3. Insert definitions of custom gates

        :return: The modified program node with injected gates and imports.
        """
        self.generic_visit(node)
        node.statements = (
            sorted(self.includes.values(), key=lambda imp: imp.filename)
            + [self.gates[gd] for gd in sorted(self.require_gates)]
            + node.statements
        )
        return node


class QASMConverter:
    """Main interface for converting OpenQASM 2.x into OpenQASM 3.1 ASTs.

    If the input code is already in OpenQASM 3.x, it is returned as-is (after parsing).
    Custom libraries for legacy gates can be provided via `CustomOpenqasmLib` and will be
    injected automatically.
    """

    custom_libs: dict[str, CustomOpenqasmLib]

    def add_custom_gate_lib(self, lib: CustomOpenqasmLib) -> None:
        """Append custom lib to internal data.

        :param lib: The custom gate library to add.
        """
        self.custom_libs[lib.name] = lib

    def __init__(self, custom_libs: list[CustomOpenqasmLib] | None = None) -> None:
        """Initialize the QASMConverter with optional external OpenQASM files for unsupported gates.

        :param custom_libs: List of CustomOpenqasmLib's containing additional gate definitions.
        """
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
        """Convert entire OpenQASM 2.x code to OpenQASM 3.1 AST or return parsed OpenQASM 3.x. directly

        Warning: All comments present in the given OpenQASM code will be removed!!!

        This method processes a OpenQASM 2.x/3.x program, transforming it into valid OpenQASM 3.x.
        The conversion process includes the following steps:

        1. Check for opaque, raise error when found
        2. Parse into AST
        3. If version 3.x, return AST
        4. If neither version 3.x nor 2.x, raise error
        5. Set version 3.1
        6. Include gates from custom libs, replace/remove obsolete imports

        :param qasm2_code: A string containing OpenQASM 2.x/3.x code to be converted.

        :return: AST in OpenQASM 3.x format.

        :raises QASMConversionError: If any line contains an unsupported OpenQASM version, library or opaque was used.
        """
        opaque = OPAQUE_STATEMENT_PATTERN.findall(qasm2_code)
        if len(opaque) != 0:
            msg = f"Unsupported opaque definition {opaque} could not be ported to OpenQASM 3."
            raise QASMConversionError(msg)

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
) -> Program:
    """Parse an OpenQASM 2.x/3.x string to an equivalent OpenQASM 3.1 AST.

    :param code: The code-string to be parsed and converted if required.
    :param custom_libs: An optional list of custom provided libraries. "qelib1.inc" is builtin.
    :return: The converted/parsed OpenQASM 3.1 AST.
    """
    custom_libs = [] if custom_libs is None else custom_libs
    return QASMConverter(custom_libs).parse_to_qasm3(code)

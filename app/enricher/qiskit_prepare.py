"""
Qiskit-backed enrichment strategy for prepare-state nodes.

This strategy generates OpenQASM implementations for prepare-state nodes
by synthesizing circuits with Qiskit (v2+). The import is guarded so
the backend still works without Qiskit installed.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import override

from openqasm3 import parse as parse_qasm
from openqasm3.ast import Identifier, Program

from app.enricher import (
    Constraints,
    EnricherStrategy,
    EnrichmentResult,
    ImplementationMetaData,
    ParsedImplementationNode,
)
from app.enricher.exceptions import (
    PrepareStateSizeOutOfRange,
    QuantumStateNotSupported,
)
from app.enricher.utils import leqo_output
from app.model.CompileRequest import Node as FrontendNode
from app.model.CompileRequest import PrepareStateNode
from app.model.exceptions import InputCountMismatch

_MIN_QISKIT_MAJOR = 2
_MIN_GHZ_SIZE = 2
_BELL_STATE_SIZE = 2

try:  # pragma: no cover - optional dependency
    import qiskit
    from qiskit.circuit import QuantumCircuit, QuantumRegister
    from qiskit.qasm3 import dumps as qasm3_dumps
except ModuleNotFoundError:  # pragma: no cover - exercised when qiskit is absent
    QuantumCircuit = None
    QuantumRegister = None
    qasm3_dumps = None
    _QISKIT_VERSION = None
else:  # pragma: no cover - exercised when qiskit is available
    _QISKIT_VERSION = getattr(qiskit, "__version__", "0")
    try:
        _QISKIT_MAJOR = int(_QISKIT_VERSION.split(".", 1)[0])
    except (ValueError, IndexError):
        _QISKIT_MAJOR = 0

    if _QISKIT_MAJOR < _MIN_QISKIT_MAJOR:
        QuantumCircuit = None
        QuantumRegister = None
        qasm3_dumps = None

HAS_QISKIT = (
    QuantumCircuit is not None
    and QuantumRegister is not None
    and qasm3_dumps is not None
)

_PHI_PLUS = "\u03d5+"
_PHI_MINUS = "\u03d5-"
_PSI_PLUS = "\u03c8+"
_PSI_MINUS = "\u03c8-"
_DEFAULT_REGISTER_NAME = "state"

# Prepare Bell states, whether x or z applies to create the state
_BELL_STATE_SWITCHES = {
    _PHI_PLUS: (False, False),
    _PHI_MINUS: (False, True),
    _PSI_PLUS: (True, False),
    _PSI_MINUS: (True, True),
}


class QiskitPrepareStateEnricherStrategy(EnricherStrategy):
    """Generate prepare-state implementations using Qiskit circuits."""

    def __init__(self, register_name: str = _DEFAULT_REGISTER_NAME) -> None:
        self._register_name = register_name

    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> Iterable[EnrichmentResult]:
        if not isinstance(node, PrepareStateNode):
            return []

        if not HAS_QISKIT:
            return []

        self._validate_constraints(node, constraints)
        circuit = self._build_circuit(node)
        program = self._build_program(circuit)

        result = EnrichmentResult(
            ParsedImplementationNode(id=node.id, implementation=program),
            ImplementationMetaData(
                width=circuit.num_qubits,
                depth=circuit.depth(),
            ),
        )
        return [result]

    def _validate_constraints(
        self, node: PrepareStateNode, constraints: Constraints | None
    ) -> None:
        if node.size <= 0:
            raise PrepareStateSizeOutOfRange(node)

        if constraints is not None and len(constraints.requested_inputs) != 0:
            raise InputCountMismatch(
                node,
                actual=len(constraints.requested_inputs),
                should_be="equal",
                expected=0,
            )

    def _build_circuit(self, node: PrepareStateNode) -> QuantumCircuit:
        assert HAS_QISKIT
        assert QuantumCircuit is not None
        assert QuantumRegister is not None

        state = node.quantumState

        if state in _BELL_STATE_SWITCHES:
            apply_x, apply_z = _BELL_STATE_SWITCHES[state]
            return self._build_bell_state(node, apply_x=apply_x, apply_z=apply_z)

        if state == "ghz":
            if node.size < _MIN_GHZ_SIZE:
                raise QuantumStateNotSupported(node)

            register = QuantumRegister(node.size, self._register_name)
            circuit = QuantumCircuit(register, name="ghz_state")
            circuit.h(register[0])
            for target in range(1, node.size):
                circuit.cx(register[0], register[target])

            return circuit

        if state == "uniform":
            register = QuantumRegister(node.size, self._register_name)
            circuit = QuantumCircuit(register, name="uniform_state")
            for idx in range(node.size):
                circuit.h(register[idx])

            return circuit

        if state == "w":
            register = QuantumRegister(node.size, self._register_name)
            # TODO
            return QuantumCircuit(register, name="w_state")

        if state == "custom":
            raise QuantumStateNotSupported(node)

        raise QuantumStateNotSupported(node)

    def _build_bell_state(
        self,
        node: PrepareStateNode,
        *,
        apply_x: bool,
        apply_z: bool,
    ) -> QuantumCircuit:
        assert HAS_QISKIT
        assert QuantumCircuit is not None
        assert QuantumRegister is not None

        if node.size != _BELL_STATE_SIZE:
            raise QuantumStateNotSupported(node)

        register = QuantumRegister(_BELL_STATE_SIZE, self._register_name)
        circuit = QuantumCircuit(register, name="bell_state")
        circuit.h(register[0])
        circuit.cx(register[0], register[1])

        if apply_x:
            circuit.x(register[1])
        if apply_z:
            circuit.z(register[0])

        return circuit

    def _build_program(self, circuit: QuantumCircuit) -> Program:
        assert HAS_QISKIT
        assert qasm3_dumps is not None

        qasm = qasm3_dumps(circuit)
        program = parse_qasm(qasm)
        program.statements.append(
            leqo_output(
                f"{self._register_name}_out",
                0,
                Identifier(self._register_name),
            )
        )
        return program


__all__ = ["HAS_QISKIT", "QiskitPrepareStateEnricherStrategy"]

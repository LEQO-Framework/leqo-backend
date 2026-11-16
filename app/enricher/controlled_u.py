"""
Qiskit-backed enrichment strategy for controlled unitary matrix nodes.

The frontend provides a unitary matrix U. This strategy builds a controlled
version of U and exports it as OpenQASM 3.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from typing import override

import numpy as np
from openqasm3 import parse as parse_qasm

from app.enricher import (
    Constraints,
    EnricherStrategy,
    EnrichmentResult,
    ImplementationMetaData,
    ParsedImplementationNode,
)
from app.enricher.exceptions import EnricherException
from app.model.CompileRequest import ControlledUNode
from app.model.CompileRequest import Node as FrontendNode
from app.model.data_types import QubitType
from app.model.exceptions import (
    InputCountMismatch,
    InputSizeMismatch,
    InputTypeMismatch,
)

_MIN_QISKIT_MAJOR = 2
_MATRIX_NDIM = 2
_CONTROLLED_U_INPUT_COUNT = 2
_CONTROL_QUBIT_COUNT = 1
_QASM_EXPORT_DECOMPOSE_REPS = 10
_CONTROL_REGISTER_NAME = "control"
_TARGET_REGISTER_NAME = "target"

try:  # pragma: no cover - optional dependency
    import qiskit
    from qiskit.circuit import QuantumCircuit, QuantumRegister
    from qiskit.circuit.library import UnitaryGate
    from qiskit.qasm3 import dumps as qasm3_dumps
except ModuleNotFoundError:  # pragma: no cover
    QuantumCircuit = None
    QuantumRegister = None
    UnitaryGate = None
    qasm3_dumps = None
    _QISKIT_VERSION = None
else:  # pragma: no cover
    _QISKIT_VERSION = getattr(qiskit, "__version__", "0")
    try:
        _QISKIT_MAJOR = int(_QISKIT_VERSION.split(".", 1)[0])
    except (ValueError, IndexError):
        _QISKIT_MAJOR = 0

    if _QISKIT_MAJOR < _MIN_QISKIT_MAJOR:
        QuantumCircuit = None
        QuantumRegister = None
        UnitaryGate = None
        qasm3_dumps = None


HAS_QISKIT_CONTROLLED_U = (
    QuantumCircuit is not None
    and QuantumRegister is not None
    and UnitaryGate is not None
    and qasm3_dumps is not None
)


class ControlledUEnricherStrategy(EnricherStrategy):
    """
    Enricher strategy for matrix-based Controlled-U nodes.
    """

    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> Iterable[EnrichmentResult]:
        if not isinstance(node, ControlledUNode):
            return []

        if not HAS_QISKIT_CONTROLLED_U:
            return []

        matrix = _validate_matrix(node)
        target_qubit_count = _target_qubit_count(matrix)
        _validate_constraints(node, constraints, target_qubit_count)

        circuit = _build_controlled_unitary_circuit(
            matrix=matrix,
            control_value=node.controlValue,
            target_qubit_count=target_qubit_count,
        )
        export_circuit = _decompose_for_qasm_export(circuit)
        program = parse_qasm(_annotated_qasm(export_circuit, target_qubit_count))

        return [
            EnrichmentResult(
                ParsedImplementationNode(id=node.id, implementation=program),
                ImplementationMetaData(
                    width=target_qubit_count + _CONTROL_QUBIT_COUNT,
                    depth=export_circuit.depth(),
                ),
            )
        ]


def _validate_matrix(node: ControlledUNode) -> np.ndarray:
    matrix = np.asarray(node.matrix, dtype=complex)

    if matrix.ndim != _MATRIX_NDIM:
        raise EnricherException("Controlled-U matrix must be two-dimensional.", node)

    rows, cols = matrix.shape
    if rows != cols:
        raise EnricherException("Controlled-U matrix must be square.", node)

    if rows == 0 or not _is_power_of_two(rows):
        raise EnricherException(
            "Controlled-U matrix dimension must be a power of two.",
            node,
        )

    identity = np.eye(rows, dtype=complex)
    if not np.allclose(matrix.conj().T @ matrix, identity):
        raise EnricherException("Controlled-U matrix must be unitary.", node)

    return matrix


def _target_qubit_count(matrix: np.ndarray) -> int:
    return int(math.log2(matrix.shape[0]))


def _is_power_of_two(value: int) -> bool:
    return value > 0 and (value & (value - 1)) == 0


def _validate_constraints(
    node: ControlledUNode,
    constraints: Constraints | None,
    target_qubit_count: int,
) -> None:
    if (
        constraints is None
        or len(constraints.requested_inputs) != _CONTROLLED_U_INPUT_COUNT
    ):
        raise InputCountMismatch(
            node,
            actual=len(constraints.requested_inputs) if constraints else 0,
            should_be="equal",
            expected=_CONTROLLED_U_INPUT_COUNT,
        )

    control_type = constraints.requested_inputs[0]
    target_type = constraints.requested_inputs[1]

    if not isinstance(control_type, QubitType):
        raise InputTypeMismatch(node, 0, actual=control_type, expected="qubit")

    if not isinstance(target_type, QubitType):
        raise InputTypeMismatch(node, 1, actual=target_type, expected="qubit")

    control_size = (
        _CONTROL_QUBIT_COUNT if control_type.size is None else control_type.size
    )
    target_size = _CONTROL_QUBIT_COUNT if target_type.size is None else target_type.size

    if control_size != _CONTROL_QUBIT_COUNT:
        raise InputSizeMismatch(
            node,
            0,
            actual=control_size,
            expected=_CONTROL_QUBIT_COUNT,
        )

    if target_size != target_qubit_count:
        raise InputSizeMismatch(
            node,
            1,
            actual=target_size,
            expected=target_qubit_count,
        )


def _build_controlled_unitary_circuit(
    *,
    matrix: np.ndarray,
    control_value: int,
    target_qubit_count: int,
) -> QuantumCircuit:
    assert HAS_QISKIT_CONTROLLED_U
    assert QuantumCircuit is not None
    assert QuantumRegister is not None
    assert UnitaryGate is not None

    control = QuantumRegister(_CONTROL_QUBIT_COUNT, _CONTROL_REGISTER_NAME)
    target = QuantumRegister(target_qubit_count, _TARGET_REGISTER_NAME)
    circuit = QuantumCircuit(control, target, name="controlled_u")

    unitary = UnitaryGate(matrix, label="u")
    controlled_unitary = unitary.control(
        _CONTROL_QUBIT_COUNT,
        ctrl_state=control_value,
    )

    circuit.append(
        controlled_unitary,
        [control[0], *[target[index] for index in range(target_qubit_count)]],
    )

    return circuit


def _decompose_for_qasm_export(circuit: QuantumCircuit) -> QuantumCircuit:
    return circuit.decompose(reps=_QASM_EXPORT_DECOMPOSE_REPS)


def _annotated_qasm(circuit: QuantumCircuit, target_qubit_count: int) -> str:
    assert HAS_QISKIT_CONTROLLED_U
    assert qasm3_dumps is not None

    qasm = qasm3_dumps(circuit)

    qasm = re.sub(
        rf"(?m)^qubit\[\s*{_CONTROL_QUBIT_COUNT}\s*\]\s+{_CONTROL_REGISTER_NAME};",
        f"@leqo.input 0\nqubit[{_CONTROL_QUBIT_COUNT}] {_CONTROL_REGISTER_NAME};",
        qasm,
        count=1,
    )
    qasm = re.sub(
        rf"(?m)^qubit\[\s*{target_qubit_count}\s*\]\s+{_TARGET_REGISTER_NAME};",
        f"@leqo.input 1\nqubit[{target_qubit_count}] {_TARGET_REGISTER_NAME};",
        qasm,
        count=1,
    )

    return (
        f"{qasm}\n"
        "@leqo.output 0\n"
        f"let control_out = {_CONTROL_REGISTER_NAME};\n"
        "@leqo.output 1\n"
        f"let target_out = {_TARGET_REGISTER_NAME};\n"
    )

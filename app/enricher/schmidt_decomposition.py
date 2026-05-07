from collections.abc import Iterable
from dataclasses import dataclass
from math import log2
from typing import Any

import numpy as np
from qiskit.quantum_info import Statevector, schmidt_decomposition

DEFAULT_TOLERANCE = 1e-10
MIN_STATE_VECTOR_LENGTH = 2
SEPARABLE_RANK = 1


@dataclass(frozen=True)
class SchmidtDecompositionResult:
    coefficients: list[float]
    rank: int
    entanglement_entropy: float
    is_separable: bool


def coerce_state_vector(raw_value: Any) -> np.ndarray:
    """Convert a raw input value into a normalized complex state vector."""
    if raw_value is None:
        raise RuntimeError("Schmidt decomposition needs a state vector input.")

    if isinstance(raw_value, str):
        parts = [
            part.strip()
            for part in raw_value.replace(";", ",").split(",")
            if part.strip() != ""
        ]
        values = [complex(part) for part in parts]
    elif isinstance(raw_value, Iterable) and not isinstance(
        raw_value, (bytes, bytearray)
    ):
        values = [complex(value) for value in raw_value]
    else:
        values = [complex(raw_value)]

    vector = np.asarray(values, dtype=complex)

    if vector.size < MIN_STATE_VECTOR_LENGTH:
        raise RuntimeError("State vector must contain at least 2 amplitudes.")

    if int(vector.size) & (int(vector.size) - 1) != 0:
        raise RuntimeError("State vector length must be a power of two.")

    norm = np.linalg.norm(vector)
    if norm == 0:
        raise RuntimeError("State vector has norm 0.")

    return vector / norm


def validate_qargs(num_qubits: int, qargs: list[int]) -> None:
    """Validate the subsystem indices used for Schmidt decomposition."""
    if not qargs:
        raise RuntimeError("qargs must contain at least one subsystem index.")

    if len(set(qargs)) != len(qargs):
        raise RuntimeError("qargs must not contain duplicate indices.")

    if any(qarg < 0 or qarg >= num_qubits for qarg in qargs):
        raise RuntimeError("qargs contains an index outside the state range.")

    if len(qargs) == num_qubits:
        raise RuntimeError("qargs must not contain all qubits.")


def analyze_schmidt_decomposition(
    raw_state_vector: Any,
    qargs: list[int],
    tolerance: float = DEFAULT_TOLERANCE,
) -> SchmidtDecompositionResult:
    """Analyze a bipartite pure quantum state using Schmidt decomposition."""
    if tolerance <= 0:
        raise RuntimeError("tolerance must be greater than 0.")

    vector = coerce_state_vector(raw_state_vector)
    num_qubits = int(vector.size).bit_length() - 1

    validate_qargs(num_qubits, qargs)

    state = Statevector(vector)
    decomposition = schmidt_decomposition(state, qargs)

    coefficients = [float(coefficient) for coefficient, _, _ in decomposition]
    probabilities = [
        coefficient**2 for coefficient in coefficients if coefficient > tolerance
    ]

    rank = len(probabilities)
    entanglement_entropy = -sum(
        probability * log2(probability) for probability in probabilities
    )

    return SchmidtDecompositionResult(
        coefficients=coefficients,
        rank=rank,
        entanglement_entropy=entanglement_entropy,
        is_separable=rank == SEPARABLE_RANK,
    )

from collections.abc import Iterable
from math import isqrt, log2
from typing import Any

import numpy as np
import openqasm3
from openqasm3 import ast
from qiskit import qasm3
from qiskit.circuit import QuantumCircuit, QuantumRegister
from qiskit.circuit.library import UnitaryGate

from app.enricher import Constraints, EnrichmentResult, ImplementationMetaData
from app.enricher.utils import implementation, leqo_output
from app.model import CompileRequest, data_types
from app.model.exceptions import InputSizeMismatch, InputTypeMismatch

MIN_MATRIX_DIMENSION = 2
DECOMPOSITION_PASSES = 4
UNITARY_ATOL = 1e-8


def _get_array_length(array_type: data_types.ArrayType | ast.ArrayType) -> int:
    if isinstance(array_type, data_types.ArrayType):
        length = array_type.length
    else:
        length = array_type.dimensions[0]

    if isinstance(length, list) and length:
        length = length[0]

    if hasattr(length, "value"):
        length = length.value

    return int(length)


def _coerce_matrix_array_value(raw_value: Any) -> list[complex]:
    actual_raw = raw_value.values if hasattr(raw_value, "values") else raw_value

    if isinstance(actual_raw, str):
        parts = [
            part.strip()
            for part in actual_raw.replace(";", ",").split(",")
            if part.strip()
        ]
        return [complex(part) for part in parts]

    if isinstance(actual_raw, Iterable) and not isinstance(
        actual_raw,
        (str, bytes, bytearray),
    ):
        return [
            complex(value.value if hasattr(value, "value") else value)
            for value in actual_raw
        ]

    if actual_raw is None:
        raise RuntimeError("Matrix encoding requires a constant array input.")

    return [complex(actual_raw.value if hasattr(actual_raw, "value") else actual_raw)]


def _reshape_and_validate_unitary_matrix(
    flat_values: list[complex],
) -> tuple[np.ndarray, int]:
    total_length = len(flat_values)
    dimension = isqrt(total_length)

    if dimension * dimension != total_length:
        raise RuntimeError(
            "Matrix encoding expects a flat square matrix "
            "(length must be n^2)."
        )

    if dimension < MIN_MATRIX_DIMENSION:
        raise RuntimeError("Matrix encoding needs at least a 2x2 matrix.")

    if dimension & (dimension - 1) != 0:
        raise RuntimeError("Matrix encoding expects a 2^n x 2^n matrix.")

    matrix = np.asarray(flat_values, dtype=complex).reshape((dimension, dimension))
    identity = np.eye(dimension, dtype=complex)

    if not np.allclose(matrix.conj().T @ matrix, identity, atol=UNITARY_ATOL):
        raise RuntimeError("Matrix encoding expects a unitary matrix.")

    n_qubits = int(log2(dimension))
    return matrix, n_qubits


def generate_matrix_enrichment(
    node: CompileRequest.EncodeValueNode,
    constraints: Constraints,
) -> EnrichmentResult:
    requested_input = constraints.requested_inputs[0]

    if not isinstance(requested_input, (data_types.ArrayType, ast.ArrayType)):
        raise InputTypeMismatch(
            node,
            input_index=0,
            actual=requested_input,
            expected="array",
        )

    input_value = constraints.requested_input_values.get(0)
    if input_value is None:
        raise RuntimeError("Matrix encoding requires a constant array input.")

    flat_values = _coerce_matrix_array_value(input_value)
    expected_length = _get_array_length(requested_input)

    if len(flat_values) != expected_length:
        raise InputSizeMismatch(
            node,
            input_index=0,
            actual=len(flat_values),
            expected=expected_length,
        )

    matrix, n_qubits = _reshape_and_validate_unitary_matrix(flat_values)

    qreg = QuantumRegister(n_qubits, "encoded")
    circuit = QuantumCircuit(qreg, name="matrix_encoding")
    circuit.append(UnitaryGate(matrix), qreg)

    for _ in range(DECOMPOSITION_PASSES):
        circuit = circuit.decompose()

    qasm_text = qasm3.dumps(circuit)
    program = openqasm3.parse(qasm_text)
    statements = list(program.statements)

    if not any(isinstance(statement, ast.Include) for statement in statements):
        statements.insert(0, ast.Include("stdgates.inc"))

    statements.append(leqo_output("out", 0, ast.Identifier("encoded")))

    return EnrichmentResult(
        implementation(node, statements),
        ImplementationMetaData(
            width=n_qubits,
            depth=circuit.depth(),
        ),
    )
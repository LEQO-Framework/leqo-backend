from collections.abc import Iterable
from math import log2
from typing import Any

import numpy as np
import openqasm3
from openqasm3 import ast
from qiskit import qasm3
from qiskit.circuit import QuantumCircuit, QuantumRegister
from qiskit.circuit.library import StatePreparation

from app.enricher import Constraints, EnrichmentResult, ImplementationMetaData
from app.enricher.exceptions import EncodingNotSupported
from app.enricher.utils import implementation, leqo_output
from app.model import CompileRequest, data_types
from app.model.exceptions import InputSizeMismatch, InputTypeMismatch

MIN_AMPLITUDE_VALUES = 2
DECOMPOSITION_PASSES = 4


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


def _coerce_amplitude_array_value(raw_value: Any) -> list[float]:
    actual_raw = raw_value.values if hasattr(raw_value, "values") else raw_value

    if isinstance(actual_raw, str):
        parts = [
            part.strip()
            for part in actual_raw.replace(";", ",").split(",")
            if part.strip()
        ]
        return [float(part) for part in parts]

    if isinstance(actual_raw, Iterable) and not isinstance(
        actual_raw,
        (str, bytes, bytearray),
    ):
        return [
            float(value.value if hasattr(value, "value") else value)
            for value in actual_raw
        ]

    if actual_raw is None:
        raise RuntimeError("Amplitude encoding requires a constant array input.")

    return [float(actual_raw.value if hasattr(actual_raw, "value") else actual_raw)]


def generate_amplitude_enrichment(
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
        raise EncodingNotSupported(node)

    values = _coerce_amplitude_array_value(input_value)
    expected_length = _get_array_length(requested_input)

    if len(values) != expected_length:
        raise InputSizeMismatch(
            node,
            input_index=0,
            actual=len(values),
            expected=expected_length,
        )

    vector = np.asarray(values, dtype=float)

    if node.bounds == 1 and (np.any(vector < 0.0) or np.any(vector > 1.0)):
        raise RuntimeError(
            "Amplitude encoding with bounds=1 expects all values in [0, 1]."
        )

    if vector.size < MIN_AMPLITUDE_VALUES:
        raise RuntimeError("Amplitude encoding needs an array with at least 2 values.")

    target_length = 1 << (int(vector.size) - 1).bit_length()
    if target_length != vector.size:
        vector = np.pad(vector, (0, target_length - vector.size), mode="constant")

    norm = np.linalg.norm(vector)
    if norm == 0:
        raise RuntimeError("Amplitude encoding input vector has norm 0.")

    vector = vector / norm

    n_qubits = int(log2(int(vector.size)))

    if n_qubits <= 0:
        raise InputSizeMismatch(
            node,
            input_index=0,
            actual=n_qubits,
            expected=1,
        )

    qreg = QuantumRegister(n_qubits, "encoded")
    circuit = QuantumCircuit(qreg, name="amplitude_encoding")
    circuit.append(StatePreparation(vector.astype(complex)), qreg)

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

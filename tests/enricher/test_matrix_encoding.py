import pytest

from app.enricher import Constraints
from app.enricher.encode_value_handlers.matrix import generate_matrix_enrichment
from app.model.CompileRequest import EncodeValueNode
from app.model.data_types import ArrayType, FloatType
from app.model.exceptions import InputTypeMismatch
from app.openqasm3.printer import leqo_dumps


def _node() -> EncodeValueNode:
    return EncodeValueNode(
        id="matrix-node",
        label=None,
        type="encode",
        encoding="matrix",
        bounds=0,
    )


def test_generate_matrix_encoding_for_pauli_x() -> None:
    constraints = Constraints(
        requested_inputs={0: ArrayType.with_size(1, 4)},
        requested_input_values={0: [0, 1, 1, 0]},
    )

    result = generate_matrix_enrichment(_node(), constraints)
    implementation_str = leqo_dumps(result.enriched_node.implementation)

    assert 'include "stdgates.inc";' in implementation_str
    assert "qubit[1] encoded;" in implementation_str
    assert "@leqo.output 0" in implementation_str
    assert "let out = encoded;" in implementation_str
    assert result.meta_data.width == 1
    assert result.meta_data.depth is not None


def test_generate_matrix_encoding_rejects_non_array_input() -> None:
    constraints = Constraints(
        requested_inputs={0: FloatType(size=32)},
        requested_input_values={0: [0, 1, 1, 0]},
    )

    with pytest.raises(InputTypeMismatch):
        generate_matrix_enrichment(_node(), constraints)


def test_generate_matrix_encoding_rejects_missing_constant_value() -> None:
    constraints = Constraints(
        requested_inputs={0: ArrayType.with_size(1, 4)},
    )

    with pytest.raises(
        RuntimeError,
        match=r"Matrix encoding requires a constant array input\.",
    ):
        generate_matrix_enrichment(_node(), constraints)


def test_generate_matrix_encoding_rejects_non_square_length() -> None:
    constraints = Constraints(
        requested_inputs={0: ArrayType.with_size(1, 3)},
        requested_input_values={0: [1, 0, 0]},
    )

    with pytest.raises(RuntimeError, match=r"flat square matrix"):
        generate_matrix_enrichment(_node(), constraints)


def test_generate_matrix_encoding_rejects_non_power_of_two_dimension() -> None:
    constraints = Constraints(
        requested_inputs={0: ArrayType.with_size(1, 9)},
        requested_input_values={0: [1, 0, 0, 0, 1, 0, 0, 0, 1]},
    )

    with pytest.raises(RuntimeError, match=r"2\^n x 2\^n"):
        generate_matrix_enrichment(_node(), constraints)


def test_generate_matrix_encoding_rejects_non_unitary_matrix() -> None:
    constraints = Constraints(
        requested_inputs={0: ArrayType.with_size(1, 4)},
        requested_input_values={0: [1, 1, 0, 1]},
    )

    with pytest.raises(RuntimeError, match=r"unitary matrix"):
        generate_matrix_enrichment(_node(), constraints)

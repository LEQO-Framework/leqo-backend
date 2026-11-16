from types import SimpleNamespace

import pytest

from app.enricher import Constraints
from app.enricher.encode_value_handlers.amplitude import generate_amplitude_enrichment
from app.model import CompileRequest, data_types
from app.model.exceptions import InputSizeMismatch, InputTypeMismatch


def _amplitude_node(bounds: int = 0) -> CompileRequest.EncodeValueNode:
    return CompileRequest.EncodeValueNode(
        id="amplitude-node",
        encoding="amplitude",
        bounds=bounds,
    )


def _constraints(
    requested_input: data_types.LeqoSupportedType,
    values: list[float] | None,
) -> Constraints:
    requested_input_values = {}
    if values is not None:
        requested_input_values[0] = SimpleNamespace(values=values)

    return Constraints(
        requested_inputs={0: requested_input},
        requested_input_values=requested_input_values,
    )


def test_amplitude_encoding_rejects_float_input() -> None:
    node = _amplitude_node()
    constraints = _constraints(
        data_types.FloatType(size=32),
        [1.0, 0.0],
    )

    with pytest.raises(InputTypeMismatch):
        generate_amplitude_enrichment(node, constraints)


def test_amplitude_encoding_rejects_array_length_mismatch() -> None:
    node = _amplitude_node()
    constraints = _constraints(
        data_types.ArrayType(
            element_type=data_types.FloatType(size=32),
            length=4,
        ),
        [1.0, 0.0],
    )

    with pytest.raises(InputSizeMismatch):
        generate_amplitude_enrichment(node, constraints)


def test_amplitude_encoding_rejects_zero_vector() -> None:
    node = _amplitude_node()
    constraints = _constraints(
        data_types.ArrayType(
            element_type=data_types.FloatType(size=32),
            length=2,
        ),
        [0.0, 0.0],
    )

    with pytest.raises(RuntimeError, match="norm 0"):
        generate_amplitude_enrichment(node, constraints)


def test_amplitude_encoding_rejects_values_outside_bounds() -> None:
    node = _amplitude_node(bounds=1)
    constraints = _constraints(
        data_types.ArrayType(
            element_type=data_types.FloatType(size=32),
            length=2,
        ),
        [1.2, 0.0],
    )

    with pytest.raises(RuntimeError, match=r"\[0, 1\]"):
        generate_amplitude_enrichment(node, constraints)


def test_amplitude_encoding_generates_state_preparation_result() -> None:
    node = _amplitude_node()
    constraints = _constraints(
        data_types.ArrayType(
            element_type=data_types.FloatType(size=32),
            length=2,
        ),
        [1.0, 0.0],
    )

    result = generate_amplitude_enrichment(node, constraints)

    assert result.meta_data.width == 1
    assert result.meta_data.depth is not None
    assert result.enriched_node is not None

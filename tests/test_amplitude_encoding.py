import pytest

from app.enricher.encode_value import EncodeValueEnricherStrategy
from app.enricher.exceptions import EncodingNotSupported
from app.model.CompileRequest import EncodeValueNode
from app.model.data_types import ArrayType, FloatType


def make_strategy():
    return object.__new__(EncodeValueEnricherStrategy)


def make_node(bounds=0):
    if hasattr(EncodeValueNode, "model_construct"):
        return EncodeValueNode.model_construct(
            id="n1",
            type="encode-value",
            encoding="amplitude",
            bounds=bounds,
        )
    return EncodeValueNode(
        id="n1",
        type="encode-value",
        encoding="amplitude",
        bounds=bounds,
    )


def make_array_type(length):
    float_type = FloatType.model_construct(size=64) if hasattr(FloatType, "model_construct") else FloatType(size=64)
    if hasattr(ArrayType, "model_construct"):
        return ArrayType.model_construct(element_type=float_type, length=length)
    return ArrayType(element_type=float_type, length=length)


def test_amplitude_input_from_list():
    strategy = make_strategy()
    arr_type = make_array_type(3)

    result = strategy._coerce_amplitude_array_value(arr_type, [1, 2, 3])

    assert result == [1.0, 2.0, 3.0]


def test_amplitude_input_from_string():
    strategy = make_strategy()
    arr_type = make_array_type(3)

    result = strategy._coerce_amplitude_array_value(arr_type, "1,2,3")

    assert result == [1.0, 2.0, 3.0]


def test_amplitude_wrong_length():
    strategy = make_strategy()
    arr_type = make_array_type(3)

    with pytest.raises(RuntimeError):
        strategy._coerce_amplitude_array_value(arr_type, [1, 2])


def test_amplitude_needs_real_input():
    strategy = make_strategy()
    node = make_node()
    arr_type = make_array_type(2)

    with pytest.raises(EncodingNotSupported):
        strategy.generate_amplitude_enrichment(node, arr_type, None)


def test_amplitude_zero_vector():
    strategy = make_strategy()
    node = make_node()
    arr_type = make_array_type(2)

    with pytest.raises(RuntimeError):
        strategy.generate_amplitude_enrichment(node, arr_type, [0, 0])


def test_amplitude_bounds_one():
    strategy = make_strategy()
    node = make_node(bounds=1)
    arr_type = make_array_type(2)

    with pytest.raises(RuntimeError):
        strategy.generate_amplitude_enrichment(node, arr_type, [1.5, 0.2])


def test_amplitude_padding_width():
    strategy = make_strategy()
    node = make_node()
    arr_type = make_array_type(3)

    result = strategy.generate_amplitude_enrichment(node, arr_type, [1, 2, 3])

    assert result.meta_data.width == 2


def test_amplitude_output_exists():
    strategy = make_strategy()
    node = make_node()
    arr_type = make_array_type(2)

    result = strategy.generate_amplitude_enrichment(node, arr_type, [1, 0])

    implementation = result.enriched_node.implementation
    text = str(implementation)

    assert "encoded" in text
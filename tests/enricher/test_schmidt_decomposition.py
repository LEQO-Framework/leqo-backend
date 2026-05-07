import numpy as np
import pytest

from app.enricher.schmidt_decomposition import (
    analyze_schmidt_decomposition,
    coerce_state_vector,
    validate_qargs,
)

BELL_STATE_RANK = 2
FOUR_AMPLITUDES = 4
TWO_QUBITS = 2


def test_product_state_is_separable() -> None:
    result = analyze_schmidt_decomposition([1, 0, 0, 0], qargs=[0])

    assert result.rank == 1
    assert result.is_separable is True
    assert np.isclose(result.entanglement_entropy, 0.0)


def test_bell_state_is_entangled() -> None:
    bell_state = [1 / np.sqrt(2), 0, 0, 1 / np.sqrt(2)]

    result = analyze_schmidt_decomposition(bell_state, qargs=[0])

    assert result.rank == BELL_STATE_RANK
    assert result.is_separable is False
    assert np.isclose(result.entanglement_entropy, 1.0)
    assert np.allclose(
        sorted(result.coefficients),
        [1 / np.sqrt(2), 1 / np.sqrt(2)],
    )


def test_state_vector_is_normalized() -> None:
    vector = coerce_state_vector([1, 1, 0, 0])

    assert np.isclose(np.linalg.norm(vector), 1.0)


def test_state_vector_accepts_string_input() -> None:
    vector = coerce_state_vector("1,0,0,1")

    assert vector.size == FOUR_AMPLITUDES
    assert np.isclose(np.linalg.norm(vector), 1.0)


def test_state_vector_accepts_semicolon_string_input() -> None:
    vector = coerce_state_vector("1;0;0;1")

    assert vector.size == FOUR_AMPLITUDES
    assert np.isclose(np.linalg.norm(vector), 1.0)


def test_rejects_missing_state_vector() -> None:
    with pytest.raises(RuntimeError, match="state vector input"):
        coerce_state_vector(None)


def test_rejects_too_short_state_vector() -> None:
    with pytest.raises(RuntimeError, match="at least 2 amplitudes"):
        coerce_state_vector([1])


def test_rejects_non_power_of_two_vector() -> None:
    with pytest.raises(RuntimeError, match="power of two"):
        coerce_state_vector([1, 0, 0])


def test_rejects_zero_vector() -> None:
    with pytest.raises(RuntimeError, match="norm 0"):
        coerce_state_vector([0, 0, 0, 0])


def test_validate_qargs_accepts_valid_partition() -> None:
    validate_qargs(num_qubits=TWO_QUBITS, qargs=[0])


def test_rejects_empty_qargs() -> None:
    with pytest.raises(RuntimeError, match="at least one"):
        validate_qargs(num_qubits=TWO_QUBITS, qargs=[])


def test_rejects_duplicate_qargs() -> None:
    with pytest.raises(RuntimeError, match="duplicate"):
        validate_qargs(num_qubits=TWO_QUBITS, qargs=[0, 0])


def test_rejects_qargs_out_of_range() -> None:
    with pytest.raises(RuntimeError, match="outside"):
        validate_qargs(num_qubits=TWO_QUBITS, qargs=[TWO_QUBITS])


def test_rejects_negative_qargs() -> None:
    with pytest.raises(RuntimeError, match="outside"):
        validate_qargs(num_qubits=TWO_QUBITS, qargs=[-1])


def test_rejects_all_qubits_as_qargs() -> None:
    with pytest.raises(RuntimeError, match="all qubits"):
        validate_qargs(num_qubits=TWO_QUBITS, qargs=[0, 1])


def test_rejects_invalid_tolerance() -> None:
    with pytest.raises(RuntimeError, match="tolerance"):
        analyze_schmidt_decomposition([1, 0, 0, 0], qargs=[0], tolerance=0)


def test_rank_uses_tolerance() -> None:
    almost_product_state = [1.0, 0.0, 0.0, 1e-12]

    result = analyze_schmidt_decomposition(
        almost_product_state,
        qargs=[0],
        tolerance=1e-10,
    )

    assert result.rank == 1
    assert result.is_separable is True

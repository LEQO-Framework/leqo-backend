import math

import pytest
from openqasm3.ast import FloatLiteral, QuantumGate

from app.enricher import Constraints
from app.enricher.exceptions import EnricherException
from app.enricher.qft import _build_qft_statements, _validate_qft_constraints
from app.model.CompileRequest import QFTNode
from app.model.data_types import IntType, QubitType
from app.model.exceptions import (
    InputCountMismatch,
    InputSizeMismatch,
    InputTypeMismatch,
)


def _only_gates(statements):
    return [stmt for stmt in statements if isinstance(stmt, QuantumGate)]


def _gate_name(stmt: QuantumGate) -> str:
    return stmt.name.name


def _qubit_indices(stmt: QuantumGate) -> list[int]:
    return [qubit.indices[0][0].value for qubit in stmt.qubits]


def _angle(stmt: QuantumGate) -> float | None:
    if not stmt.arguments:
        return None
    arg = stmt.arguments[0]
    assert isinstance(arg, FloatLiteral)
    return arg.value


def test_build_qft_statements_size_1_forward() -> None:
    statements = _only_gates(_build_qft_statements(1, inverse=False))

    assert [_gate_name(stmt) for stmt in statements] == ["h"]
    assert _qubit_indices(statements[0]) == [0]


def test_build_qft_statements_size_1_inverse() -> None:
    statements = _only_gates(_build_qft_statements(1, inverse=True))

    assert [_gate_name(stmt) for stmt in statements] == ["h"]
    assert _qubit_indices(statements[0]) == [0]


def test_build_qft_statements_size_2_forward_sequence() -> None:
    statements = _only_gates(_build_qft_statements(2, inverse=False))

    assert [_gate_name(stmt) for stmt in statements] == ["h", "cp", "h", "swap"]

    assert _qubit_indices(statements[0]) == [0]
    assert _qubit_indices(statements[1]) == [1, 0]
    assert _angle(statements[1]) == pytest.approx(math.pi / 2)
    assert _qubit_indices(statements[2]) == [1]
    assert _qubit_indices(statements[3]) == [0, 1]


def test_build_qft_statements_size_2_inverse_sequence() -> None:
    statements = _only_gates(_build_qft_statements(2, inverse=True))

    assert [_gate_name(stmt) for stmt in statements] == ["swap", "h", "cp", "h"]

    assert _qubit_indices(statements[0]) == [0, 1]
    assert _qubit_indices(statements[1]) == [1]
    assert _qubit_indices(statements[2]) == [1, 0]
    assert _angle(statements[2]) == pytest.approx(-math.pi / 2)
    assert _qubit_indices(statements[3]) == [0]


def test_qft_size_3_has_expected_gate_count() -> None:
    statements = _only_gates(_build_qft_statements(3, inverse=False))

    expected_gate_count = 7
    expected_h_count = 3
    expected_cp_count = 3
    expected_swap_count = 1

    assert len(statements) == expected_gate_count
    assert sum(1 for stmt in statements if _gate_name(stmt) == "h") == expected_h_count
    assert (
        sum(1 for stmt in statements if _gate_name(stmt) == "cp") == expected_cp_count
    )
    assert (
        sum(1 for stmt in statements if _gate_name(stmt) == "swap")
        == expected_swap_count
    )


def test_qft_size_3_has_expected_cp_angles() -> None:
    statements = _only_gates(_build_qft_statements(3, inverse=False))

    cp_angles = [_angle(stmt) for stmt in statements if _gate_name(stmt) == "cp"]

    assert cp_angles == pytest.approx(
        [
            math.pi / 2,
            math.pi / 4,
            math.pi / 2,
        ]
    )


def test_inverse_qft_size_3_has_negated_cp_angles() -> None:
    forward = _only_gates(_build_qft_statements(3, inverse=False))
    inverse = _only_gates(_build_qft_statements(3, inverse=True))

    forward_cp_angles = sorted(
        _angle(stmt) for stmt in forward if _gate_name(stmt) == "cp"
    )
    inverse_cp_angles = sorted(
        _angle(stmt) for stmt in inverse if _gate_name(stmt) == "cp"
    )

    assert len(forward_cp_angles) == len(inverse_cp_angles)

    for fwd, inv in zip(forward_cp_angles, reversed(inverse_cp_angles), strict=True):
        assert inv == pytest.approx(-fwd)


def test_qft_puts_swaps_at_end() -> None:
    statements = _only_gates(_build_qft_statements(3, inverse=False))

    assert _gate_name(statements[-1]) == "swap"


def test_inverse_qft_puts_swaps_at_beginning() -> None:
    statements = _only_gates(_build_qft_statements(3, inverse=True))

    assert _gate_name(statements[0]) == "swap"


def test_qft_constraints_derive_size_from_input_register() -> None:
    expected_size = 2
    node = QFTNode(id="nodeId")
    constraints = Constraints(
        requested_inputs={0: QubitType(expected_size)},
        optimizeWidth=False,
        optimizeDepth=False,
    )

    assert _validate_qft_constraints(constraints, node) == expected_size


def test_qft_constraints_accept_matching_explicit_size() -> None:
    expected_size = 2
    node = QFTNode(id="nodeId", size=expected_size)
    constraints = Constraints(
        requested_inputs={0: QubitType(expected_size)},
        optimizeWidth=False,
        optimizeDepth=False,
    )

    assert _validate_qft_constraints(constraints, node) == expected_size


def test_qft_constraints_reject_mismatching_explicit_size() -> None:
    input_size = 2
    expected_node_size = 3
    node = QFTNode(id="nodeId", size=expected_node_size)
    constraints = Constraints(
        requested_inputs={0: QubitType(input_size)},
        optimizeWidth=False,
        optimizeDepth=False,
    )

    with pytest.raises(
        InputSizeMismatch,
        match=r"^Expected size 3 for input 0\. Got 2\.$",
    ):
        _validate_qft_constraints(constraints, node)


@pytest.mark.parametrize(
    "constraints",
    [
        None,
        Constraints(
            requested_inputs={},
            optimizeWidth=False,
            optimizeDepth=False,
        ),
    ],
)
def test_qft_constraints_require_an_input_register(
    constraints: Constraints | None,
) -> None:
    node = QFTNode(id="nodeId")

    with pytest.raises(
        InputCountMismatch,
        match=r"^Node should have 1 inputs\. Got 0\.$",
    ):
        _validate_qft_constraints(constraints, node)


def test_qft_constraints_reject_multiple_input_registers() -> None:
    node = QFTNode(id="nodeId")
    constraints = Constraints(
        requested_inputs={0: QubitType(1), 1: QubitType(1)},
        optimizeWidth=False,
        optimizeDepth=False,
    )

    with pytest.raises(
        InputCountMismatch,
        match=r"^Node should have 1 inputs\. Got 2\.$",
    ):
        _validate_qft_constraints(constraints, node)


def test_qft_constraints_reject_non_qubit_input() -> None:
    node = QFTNode(id="nodeId")
    constraints = Constraints(
        requested_inputs={0: IntType(32)},
        optimizeWidth=False,
        optimizeDepth=False,
    )

    with pytest.raises(
        InputTypeMismatch,
        match=r"^Expected type 'qubit' for input 0\.",
    ):
        _validate_qft_constraints(constraints, node)


def test_qft_constraints_reject_missing_input_index_zero() -> None:
    node = QFTNode(id="nodeId")
    constraints = Constraints(
        requested_inputs={1: QubitType(2)},
        optimizeWidth=False,
        optimizeDepth=False,
    )

    with pytest.raises(
        EnricherException,
        match=r"^Could not determine input type for QFT input 0$",
    ):
        _validate_qft_constraints(constraints, node)

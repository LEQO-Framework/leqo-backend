import math

import pytest
from openqasm3.ast import FloatLiteral, QuantumGate

# Adjust this import path to your real module location if needed.
from app.enricher.qft import _build_qft_statements


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


def _only_gates(statements):
    return [stmt for stmt in statements if isinstance(stmt, QuantumGate)]


def test_build_qft_statements_size_2_forward_sequence():
    statements = _only_gates(_build_qft_statements(2, inverse=False))

    assert [_gate_name(stmt) for stmt in statements] == ["h", "cp", "h", "swap"]

    assert _qubit_indices(statements[0]) == [0]
    assert _qubit_indices(statements[1]) == [1, 0]
    assert _angle(statements[1]) == pytest.approx(math.pi / 2)
    assert _qubit_indices(statements[2]) == [1]
    assert _qubit_indices(statements[3]) == [0, 1]


def test_build_qft_statements_size_2_inverse_sequence():
    statements = _only_gates(_build_qft_statements(2, inverse=True))

    assert [_gate_name(stmt) for stmt in statements] == ["swap", "h", "cp", "h"]

    assert _qubit_indices(statements[0]) == [0, 1]
    assert _qubit_indices(statements[1]) == [1]
    assert _qubit_indices(statements[2]) == [1, 0]
    assert _angle(statements[2]) == pytest.approx(-math.pi / 2)
    assert _qubit_indices(statements[3]) == [0]


def test_qft_and_iqft_have_same_gate_count_size_3():
    forward = _only_gates(_build_qft_statements(3, inverse=False))
    inverse = _only_gates(_build_qft_statements(3, inverse=True))

    assert len(forward) == len(inverse)

    # For size 3:
    # 3 H gates + 3 CP gates + 1 SWAP = 7 total
   # assert len(forward) == 7  # noqa: ERA001

   # For size 3:
# 3 H gates + 3 CP gates + 1 SWAP = 7 total
    expected_gate_count = 7
    assert len(forward) == expected_gate_count


def test_inverse_qft_negates_cp_angles_size_3():
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



def _stmt_to_qasm(stmt: QuantumGate) -> str:
    gate = _gate_name(stmt)
    qubits = ", ".join(f"q[{idx}]" for idx in _qubit_indices(stmt))

    if stmt.arguments:
        args = ", ".join(str(arg.value) for arg in stmt.arguments)
        return f"{gate}({args}) {qubits};"

    return f"{gate} {qubits};"


def test_print_qft_statements_size_3():
    statements = _only_gates(_build_qft_statements(3, inverse=False))

    print("\nForward QFT:")
    for stmt in statements:
        print(_stmt_to_qasm(stmt))


def test_print_iqft_statements_size_3():
    statements = _only_gates(_build_qft_statements(3, inverse=True))

    print("\nInverse QFT:")
    for stmt in statements:
        print(_stmt_to_qasm(stmt))

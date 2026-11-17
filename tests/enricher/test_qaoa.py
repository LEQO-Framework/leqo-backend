import cmath

import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from app.algorithm_selection.qasm_service import program_to_qasm2
from app.enricher import Constraints
from app.enricher.qaoa import QAOAEnricherStrategy
from app.model.CompileRequest import QAOANode
from app.openqasm3.printer import leqo_dumps


@pytest.mark.asyncio
async def test_qaoa_maxcut_ansatz():
    """
    Tests if the QAOA Strategy correctly unrolls the Cost and Mixer
    Hamiltonians for a 3-node graph with 2 layers (p=2) using MaxCut.
    """
    node = QAOANode(
        id="qaoa-1",
        type="qaoa",
        p=2,
        problem="MaxCut",
        optimizer="COBYLA",
        edges="[[0,1], [1,2]]",
        gamma="0.5, 0.6",
        beta="0.2, 0.3",
        outputIdentifier="q_qaoa",
    )
    strategy = QAOAEnricherStrategy()
    results = strategy._enrich_impl(node, Constraints(requested_inputs={}))
    qasm = leqo_dumps(results[0].enriched_node.implementation)

    assert "qubit[3] q_qaoa;" in qasm
    assert "h q_qaoa[0];" in qasm

    # Layer 0 MaxCut: standard ZZ coupling
    assert "cx q_qaoa[0], q_qaoa[1];" in qasm
    assert "rz(0.5) q_qaoa[1];" in qasm

    # Layer 1 MaxCut
    assert "rz(0.6) q_qaoa[1];" in qasm
    assert "rx(0.6) q_qaoa[2];" in qasm


@pytest.mark.asyncio
async def test_qaoa_max2sat_ansatz():
    """
    Tests if Max-2-SAT injects single-qubit bias rotations along with the
    interacting ZZ gate sequences.
    """
    node = QAOANode(
        id="qaoa-2",
        type="qaoa",
        p=1,
        problem="Max2SAT",
        optimizer="SPSA",
        edges="[[0,1]]",
        gamma="0.4",
        beta="0.1",
        outputIdentifier="q_sat",
    )
    strategy = QAOAEnricherStrategy()
    results = strategy._enrich_impl(node, Constraints(requested_inputs={}))
    qasm = leqo_dumps(results[0].enriched_node.implementation)

    # Verify single qubit bias rotations exist for the nodes in the clauses
    assert "rz(0.4) q_sat[0];" in qasm
    assert "rz(0.4) q_sat[1];" in qasm

    # Verify coupling collection accompanies it
    assert "cx q_sat[0], q_sat[1];" in qasm
    assert "rz(0.4) q_sat[1];" in qasm


@pytest.mark.asyncio
async def test_qaoa_graph_coloring_ansatz():
    """
    Tests if Graph Coloring produces inverted negative interactions phase angles
    to accurately implement structural conflict penalties.
    """
    node = QAOANode(
        id="qaoa-3",
        type="qaoa",
        p=1,
        problem="GraphColoring",
        optimizer="NELDER_MEAD",
        edges="[[0,1]]",
        gamma="0.7",
        beta="0.25",
        outputIdentifier="q_color",
    )
    strategy = QAOAEnricherStrategy()
    results = strategy._enrich_impl(node, Constraints(requested_inputs={}))
    qasm = leqo_dumps(results[0].enriched_node.implementation)

    assert "rz(-0.7) q_color[1];" in qasm


@pytest.mark.asyncio
async def test_qaoa_edge_cases_and_fallback():
    """
    Tests the fallback mechanisms of the QAOA Strategy:
    1. Invalid edge strings should default to a 2-qubit system with edge [[0, 1]].
    2. Missing/short gamma and beta lists should pad themselves to length `p`.
    """
    node = QAOANode(
        id="qaoa-edge",
        type="qaoa",
        p=3,
        problem="MaxCut",
        optimizer="COBYLA",
        edges="an_invalid_edge_string",  # Should trigger Exception and fallback to [[0, 1]]
        gamma="0.7",  # Only 1 value provided for 3 layers
        beta="",  # No values provided, fallback to default 0.2
        outputIdentifier="q_edge",
    )

    strategy = QAOAEnricherStrategy()
    results = strategy._enrich_impl(node, Constraints(requested_inputs={}))
    qasm = leqo_dumps(results[0].enriched_node.implementation)

    # 1. Fallback to 2 qubits due to invalid edge string
    assert "qubit[2] q_edge;" in qasm
    assert "cx q_edge[0], q_edge[1];" in qasm

    # 2. Gamma padding:
    expected_gamma_count = 3
    assert qasm.count("rz(0.7)") == expected_gamma_count

    # 3. Beta defaulting and padding:
    # Empty beta list falls back to 0.2.
    # Mixer multiplies by 2.0 (0.2 * 2.0 = 0.4).
    # Applied to 2 qubits across 3 layers = 6 total rx(0.4) gates.
    assert "rx(0.4) q_edge[0];" in qasm

    expected_beta_count = 6
    assert qasm.count("rx(0.4)") == expected_beta_count


@pytest.mark.asyncio
async def test_qaoa_max2sat_with_polarity_cnf():
    """
    Tests if Max-2-SAT supports DIMACS signed literals convention to declare
    variable polarities (e.g., negative integers invert the RZ rotation angles).
    """
    node = QAOANode(
        id="qaoa-polarity",
        type="qaoa",
        p=1,
        problem="Max2SAT",
        optimizer="SPSA",
        edges="[[1, -2]]",  # x0 OR NOT x1
        gamma="0.4",
        beta="0.1",
        outputIdentifier="q_polar",
    )
    strategy = QAOAEnricherStrategy()
    results = strategy._enrich_impl(node, Constraints(requested_inputs={}))
    qasm = leqo_dumps(results[0].enriched_node.implementation)

    # (1) maps to positive rotation on qubit 0
    assert "rz(0.4) q_polar[0];" in qasm

    # (-2) maps to inverted negative rotation on qubit 1
    assert "rz(-0.4) q_polar[1];" in str(qasm)

    # sign_u * sign_v (1 * -1 = -1)
    assert "rz(-0.4) q_polar[1];" in qasm


QUBO_MATRIX = [[-1.0, 2.0, 0.0], [0.0, 1.0, -3.0], [0.0, 0.0, 0.5]]


def qubo_node(p: int, gamma: str, beta: str) -> QAOANode:
    return QAOANode(
        id="qaoa-qubo",
        type="qaoa",
        p=p,
        problem="QUBO",
        optimizer="COBYLA",
        edges="[[0, 1, 2.0], [1, 2, -3.0]]",
        linear="[-1.0, 1.0, 0.5]",
        gamma=gamma,
        beta=beta,
        outputIdentifier="q",
    )


def qubo_value(x: list[int]) -> float:
    n = len(QUBO_MATRIX)
    return sum(QUBO_MATRIX[i][j] * x[i] * x[j] for i in range(n) for j in range(n))


@pytest.mark.asyncio
async def test_qaoa_qubo_cost_layer_has_qubo_phases():
    """
    Tests if the QUBO cost layer applies the phase exp(-i gamma f(x)) to every basis state |x>,
    up to a global phase, so that the circuit encodes the weights and linear terms of the QUBO.
    """
    gamma = 0.3
    strategy = QAOAEnricherStrategy()
    results = strategy._enrich_impl(
        qubo_node(1, str(gamma), "0"), Constraints(requested_inputs={})
    )
    circuit = QuantumCircuit.from_qasm_str(
        program_to_qasm2(results[0].enriched_node.implementation)
    )
    circuit.remove_final_measurements()
    amplitudes = Statevector(circuit).data

    n = len(QUBO_MATRIX)
    for k, amplitude in enumerate(amplitudes):
        x = [(k >> i) & 1 for i in range(n)]
        expected = cmath.exp(-1j * gamma * (qubo_value(x) - qubo_value([0] * n)))
        assert amplitude / amplitudes[0] == pytest.approx(expected)


@pytest.mark.asyncio
async def test_qaoa_qubo_gate_structure():
    """
    Tests if every QUBO layer has one ZZ interaction per coupling, one RZ per local field
    and the mixer rx(2 beta).
    """
    layers = 2
    strategy = QAOAEnricherStrategy()
    results = strategy._enrich_impl(
        qubo_node(layers, "0.5, 0.6", "0.2, 0.3"), Constraints(requested_inputs={})
    )
    qasm = leqo_dumps(results[0].enriched_node.implementation)

    assert "qubit[3] q;" in qasm
    assert qasm.count("cx ") == 2 * 2 * layers
    # J_01 = 2 / 4 -> rz(2 * 0.5 * 0.5)
    assert "rz(0.5) q[1];" in qasm
    # h_0 = 1 / 2 - 2 / 4 = 0 needs no gate, h_1 = -1 / 2 - 2 / 4 + 3 / 4 and h_2 = -1 / 4 + 3 / 4
    assert qasm.count("rz(") == (2 + 2) * layers
    assert "rx(0.4) q[0];" in qasm
    assert "rx(0.6) q[2];" in qasm


@pytest.mark.parametrize(
    ("edges", "linear"),
    [("[[0, 1]]", "[1, 1]"), ("[[0, 0, 1.0]]", ""), ("[[0, 1, 1.0]]", "nope")],
)
def test_qaoa_qubo_rejects_malformed_input(edges: str, linear: str):
    node = qubo_node(1, "", "").model_copy(update={"edges": edges, "linear": linear})
    with pytest.raises(ValueError, match="QUBO"):
        QAOAEnricherStrategy()._enrich_impl(node, Constraints(requested_inputs={}))

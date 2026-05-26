import pytest

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

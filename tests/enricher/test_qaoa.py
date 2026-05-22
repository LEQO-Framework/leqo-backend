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
    assert "rx(0.3) q_qaoa[2];" in qasm


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

    # Verify that the phase rotation parameter gets flipped to a negative float
    assert "rz(-0.7) q_color[1];" in qasm
    assert "rx(0.25) q_color[0];" in qasm

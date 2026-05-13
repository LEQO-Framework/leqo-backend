import pytest
from pydantic import ValidationError

from app.enricher import Constraints
from app.enricher.grover_algorithm import GroverAlgorithmEnricherStrategy
from app.model.CompileRequest import GroverNode
from app.openqasm3.printer import leqo_dumps


@pytest.mark.asyncio
async def test_complete_grover_algorithm():
    # Setup a 2-qubit Grover search looking for state |01> (Index 1) explicitly requesting 1 iteration
    node = GroverNode(
        id="grover-1", type="grover", numQubits=2, targetStates=[1], numIterations=1
    )
    strategy = GroverAlgorithmEnricherStrategy()
    results = strategy._enrich_impl(node, Constraints(requested_inputs={}))

    qasm = leqo_dumps(results[0].enriched_node.implementation)

    # Assert 1: It declares fresh qubits (no @leqo.input 0)
    assert "@leqo.input" not in qasm
    assert "qubit[2] query;" in qasm

    # Assert 2: Initialization step (H on all qubits)
    assert "h query[0];" in qasm
    assert "h query[1];" in qasm

    # Assert 3: Oracle step (Marks |01> by applying X to q0, then MCZ)
    expected_oracle = (
        "x query[0];\nh query[1];\nmcx query[0], query[1];\nh query[1];\nx query[0];"
    )
    assert expected_oracle in qasm

    # Assert 4: Diffuser step (H -> X -> MCZ -> X -> H)
    expected_diffuser_start = "h query[0];\nh query[1];\nx query[0];\nx query[1];"
    assert expected_diffuser_start in qasm

    # Assert 5: It correctly outputs the register
    assert "@leqo.output 0" in qasm
    assert "let out = query;" in qasm


@pytest.mark.asyncio
async def test_grover_auto_iterations():
    # Setup a 3-qubit Grover search looking for 1 state, NO iterations specified.
    # N=8, M=1. Optimal exact geometric calculation is 2 iterations.
    node = GroverNode(
        id="grover-auto",
        type="grover",
        numQubits=3,
        targetStates=[1],
        numIterations=None,
    )
    strategy = GroverAlgorithmEnricherStrategy()
    results = strategy._enrich_impl(node, Constraints(requested_inputs={}))

    qasm = leqo_dumps(results[0].enriched_node.implementation)

    diffuser_signature = (
        "h query[0];\nh query[1];\nh query[2];\nx query[0];\nx query[1];\nx query[2];"
    )

    EXPECTED_ITERATIONS = 2
    assert qasm.count(diffuser_signature) == EXPECTED_ITERATIONS


def test_grover_validation_error():
    # Attempting to query an out-of-bounds state (5) on a 2-qubit system (max 3) should fail
    with pytest.raises(ValidationError):
        GroverNode(
            id="g-err", type="grover", numQubits=2, targetStates=[5], numIterations=1
        )

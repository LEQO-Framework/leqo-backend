import pytest

from app.enricher import Constraints
from app.enricher.mcmt_gate import MCMTGateEnricherStrategy
from app.model.CompileRequest import MCMTGateNode
from app.openqasm3.printer import leqo_dumps


@pytest.mark.asyncio
async def test_mcmt_gate_standard():
    node = MCMTGateNode(
        id="mcmt-1",
        type="mcmt-gate",
        baseGate="h",
        numControls=2,
        numTargets=2,
    )
    strategy = MCMTGateEnricherStrategy()
    results = strategy._enrich_impl(node, Constraints(requested_inputs={}))

    qasm = leqo_dumps(results[0].enriched_node.implementation)

    # Check that individual control and target inputs were declared correctly
    assert "qubit[1] ctrl_0;" in qasm
    assert "qubit[1] ctrl_1;" in qasm
    assert "qubit[1] target_0;" in qasm
    assert "qubit[1] target_1;" in qasm

    # Check that the ctrl modifier uses the dynamic wire names
    assert "ctrl(2) @ h ctrl_0[0], ctrl_1[0], target_0[0];" in qasm
    assert "ctrl(2) @ h ctrl_0[0], ctrl_1[0], target_1[0];" in qasm


@pytest.mark.asyncio
async def test_mcmt_gate_parameterized():
    node = MCMTGateNode(
        id="mcmt-2",
        type="mcmt-gate",
        baseGate="rx",
        numControls=1,
        numTargets=1,
        parameter=1.57,
    )
    strategy = MCMTGateEnricherStrategy()
    results = strategy._enrich_impl(node, Constraints(requested_inputs={}))

    qasm = leqo_dumps(results[0].enriched_node.implementation)

    # Check for the parameterized control using the new dynamic names
    assert "ctrl(1) @ rx(1.57) ctrl_0[0], target_0[0];" in qasm

@pytest.mark.asyncio
async def test_mcmt_gate_large_unrolling():
    """
    Tests if the compiler correctly unrolls a 1-control, 5-target gate
    into 5 sequential operations.
    """
    node = MCMTGateNode(
        id="mcmt-3",
        type="mcmt-gate",
        baseGate="x",
        numControls=1,
        numTargets=5,
    )
    strategy = MCMTGateEnricherStrategy()
    results = strategy._enrich_impl(node, Constraints(requested_inputs={}))

    qasm = leqo_dumps(results[0].enriched_node.implementation)

    # Verify all targets are declared
    assert "qubit[1] target_0;" in qasm
    assert "qubit[1] target_4;" in qasm

    # Verify the unrolling happened 5 times
    assert "ctrl(1) @ x ctrl_0[0], target_0[0];" in qasm
    assert "ctrl(1) @ x ctrl_0[0], target_1[0];" in qasm
    assert "ctrl(1) @ x ctrl_0[0], target_2[0];" in qasm
    assert "ctrl(1) @ x ctrl_0[0], target_3[0];" in qasm
    assert "ctrl(1) @ x ctrl_0[0], target_4[0];" in qasm


@pytest.mark.asyncio
async def test_mcmt_gate_array_passthrough():
    """
    Tests the logic we discovered with the Prepare State node.
    If the incoming wire is an array (size > 1), the MCMT gate must
    declare that specific wire with the larger size to avoid index errors.
    """
    # Create a mock input type to simulate a wire of size 3 (like a GHZ state)
    class MockInputType:
        def __init__(self, size):
            self.size = size

    node = MCMTGateNode(
        id="mcmt-4",
        type="mcmt-gate",
        baseGate="z",
        numControls=1,
        numTargets=1,
    )
    strategy = MCMTGateEnricherStrategy()
    
    # Input index 0 is the control (default size 1)
    # Input index 1 is the target. We tell the constraints it has size 3.
    mock_constraints = Constraints(requested_inputs={1: MockInputType(3)})
    
    results = strategy._enrich_impl(node, mock_constraints)
    qasm = leqo_dumps(results[0].enriched_node.implementation)

    # Check that the control wire is size 1
    assert "qubit[1] ctrl_0;" in qasm
    
    # Check that the target wire was dynamically resized to 3 to hold the array!
    assert "qubit[3] target_0;" in qasm
    
    # Check that the gate still applied to the 0th index of the array
    assert "ctrl(1) @ z ctrl_0[0], target_0[0];" in qasm


@pytest.mark.asyncio
async def test_mcmt_gate_no_parameter_fallback():
    """
    Tests what happens if a user selects a parameterized gate like 'RY'
    but the frontend sends a null/missing parameter. It should not crash.
    """
    node = MCMTGateNode(
        id="mcmt-5",
        type="mcmt-gate",
        baseGate="ry",
        numControls=1,
        numTargets=1,
        parameter=None, # Missing parameter
    )
    strategy = MCMTGateEnricherStrategy()
    results = strategy._enrich_impl(node, Constraints(requested_inputs={}))

    qasm = leqo_dumps(results[0].enriched_node.implementation)

    # It should fallback gracefully without throwing a Python NoneType error
    # OpenQASM will just receive the gate without arguments
    assert "ctrl(1) @ ry ctrl_0[0], target_0[0];" in qasm

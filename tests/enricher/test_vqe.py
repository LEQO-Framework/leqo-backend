import pytest

from app.enricher import Constraints
from app.enricher.vqe import VQEEnricherStrategy
from app.model.CompileRequest import VQENode
from app.openqasm3.printer import leqo_dumps


@pytest.mark.asyncio
async def test_vqe_ansatz_generation_and_padding():
    """
    Tests if the VQE Strategy unrolls a Hardware-Efficient Ansatz for 2 qubits
    with 1 layer, and verifies that short parameter lists pad correctly with 0.1.
    """
    node = VQENode(
        id="vqe-1",
        type="vqe",
        numQubits=2,
        ansatz="HardwareEfficient",
        layers=1,
        parameters="1.5, 2.5",  # Only 2 parameters provided, needs 4 total (2 per layer + initial)
        observable="Z0Z1",
        optimizer="ParameterShift",
        outputIdentifier="vqe_reg",
    )
    strategy = VQEEnricherStrategy()
    results = strategy._enrich_impl(node, Constraints(requested_inputs={}))
    qasm = leqo_dumps(results[0].enriched_node.implementation)

    assert "qubit[2] vqe_reg;" in qasm
    
    # Initial rotation layer (uses user params)
    assert "ry(1.5) vqe_reg[0];" in qasm
    assert "ry(2.5) vqe_reg[1];" in qasm
    
    # Entanglement chain
    assert "cx vqe_reg[0], vqe_reg[1];" in qasm
    
    # Ansatz layer padding (pads with 0.1)
    assert "ry(0.1) vqe_reg[0];" in qasm
    assert "ry(0.1) vqe_reg[1];" in qasm


@pytest.mark.asyncio
async def test_vqe_no_params_fallback():
    """
    Tests if providing NO parameters generates a fully 0.1 padded circuit.
    3 Qubits, 2 Layers = 3 * (2+1) = 9 parameters expected.
    """
    node = VQENode(
        id="vqe-2",
        type="vqe",
        numQubits=3,
        ansatz="HardwareEfficient",
        layers=2,
        parameters="",
        observable="Z0",
        optimizer="COBYLA",
        outputIdentifier="vqe_reg"
    )
    strategy = VQEEnricherStrategy()
    results = strategy._enrich_impl(node, Constraints(requested_inputs={}))
    qasm = leqo_dumps(results[0].enriched_node.implementation)

    assert "qubit[3] vqe_reg;" in qasm
    
    # Total padded parameters should be 9
    expected_param_count = 9
    assert qasm.count("ry(0.1)") == expected_param_count
    
    # Total CX gates should be 4 (2 entanglement gates per layer * 2 layers)
    expected_cx_count = 4
    assert qasm.count("cx") == expected_cx_count

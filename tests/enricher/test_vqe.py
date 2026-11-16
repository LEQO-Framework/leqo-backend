import pytest

from app.enricher import Constraints
from app.enricher.vqe import VQEEnricherStrategy
from app.model.CompileRequest import VQENode
from app.openqasm3.printer import leqo_dumps


@pytest.mark.asyncio
async def test_vqe_ansatz_generation():
    """
    Tests if the VQE Strategy unrolls a Hardware-Efficient Ansatz for 2 qubits
    with 1 layer, using exact parameters.
    """
    node = VQENode(
        id="vqe-1",
        type="vqe",
        numQubits=2,
        ansatz="HardwareEfficient",
        layers=1,
        parameters="1.5, 2.5, 3.5, 4.5",  # 2 qubits * (1 + 1) layers = 4 required params
        observable="Z0Z1",
        optimizer="ParameterShift",
        outputIdentifier="vqe_reg",
    )
    strategy = VQEEnricherStrategy()
    results = strategy._enrich_impl(node, Constraints(requested_inputs={}))
    qasm = leqo_dumps(results[0].enriched_node.implementation)

    assert "qubit[2] vqe_reg;" in qasm

    assert "@leqo.optimizer ParameterShift" in qasm
    assert '@leqo.observable "Z0Z1"' in qasm

    # Initial rotation layer
    assert "ry(1.5) vqe_reg[0];" in qasm
    assert "ry(2.5) vqe_reg[1];" in qasm

    # Entanglement chain
    assert "cx vqe_reg[0], vqe_reg[1];" in qasm

    # Next rotation layer
    assert "ry(3.5) vqe_reg[0];" in qasm
    assert "ry(4.5) vqe_reg[1];" in qasm

    # depth calculation: 1 + p * n -> 1 + 1 * 2 = 3
    assert results[0].meta_data.depth == 3  # noqa: PLR2004


@pytest.mark.asyncio
async def test_vqe_no_params_fallback():
    """
    Tests if providing NO parameters generates a fully 0.1 padded circuit.
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
        outputIdentifier="vqe_reg",
    )
    strategy = VQEEnricherStrategy()
    results = strategy._enrich_impl(node, Constraints(requested_inputs={}))
    qasm = leqo_dumps(results[0].enriched_node.implementation)

    # 3 Qubits, 2 Layers = 3 * (2+1) = 9 parameters expected.
    expected_param_count = 9
    assert qasm.count("ry(0.1)") == expected_param_count

    # Depth check: 1 + 2 * 3 = 7
    assert results[0].meta_data.depth == 7  # noqa: PLR2004


@pytest.mark.asyncio
async def test_vqe_malformed_params_error():
    """
    Tests if providing an incorrect number of parameters raises a ValueError.
    """
    node = VQENode(
        id="vqe-3",
        type="vqe",
        numQubits=2,
        ansatz="HardwareEfficient",
        layers=1,
        parameters="1.5, 2.5",  # Only 2 provided, 4 expected
        observable="Z0Z1",
        optimizer="ParameterShift",
        outputIdentifier="vqe_reg",
    )
    strategy = VQEEnricherStrategy()
    with pytest.raises(ValueError, match="Malformed parameters"):
        strategy._enrich_impl(node, Constraints(requested_inputs={}))


@pytest.mark.asyncio
async def test_vqe_unsupported_ansatz_error():
    """
    Tests if providing an unsupported ansatz raises a ValueError via the dispatcher.
    """
    node = VQENode(
        id="vqe-4",
        type="vqe",
        numQubits=2,
        ansatz="RyRz",
        layers=1,
        parameters="",
        observable="Z0Z1",
        optimizer="ParameterShift",
        outputIdentifier="vqe_reg",
    )
    strategy = VQEEnricherStrategy()
    with pytest.raises(ValueError, match="is currently not supported"):
        strategy._enrich_impl(node, Constraints(requested_inputs={}))

import pytest
from app.enricher import Constraints
from app.enricher.grover_algorithm import GroverAlgorithmEnricherStrategy
from app.model.CompileRequest import GroverNode
from app.openqasm3.printer import leqo_dumps
from pydantic import ValidationError

@pytest.mark.asyncio
async def test_complete_grover_algorithm():
    # Setup a 2-qubit Grover search looking for state |01> (Truth table: 0100)
    node = GroverNode(
        id="grover-1", 
        type="grover", 
        numQubits=2, 
        truthTable="0100", 
        numIterations=1
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
        'x query[0];\n'
        'h query[1];\n'
        'mcx query[0], query[1];\n'
        'h query[1];\n'
        'x query[0];'
    )
    assert expected_oracle in qasm

    # Assert 4: Diffuser step (H -> X -> MCZ -> X -> H)
    expected_diffuser_start = (
        'h query[0];\n'
        'h query[1];\n'
        'x query[0];\n'
        'x query[1];'
    )
    assert expected_diffuser_start in qasm
    
    # Assert 5: It correctly outputs the register
    assert "@leqo.output 0" in qasm
    assert "let out = query;" in qasm

def test_grover_validation_error():
    # Attempting to create a node with mismatched truth table length should fail
    with pytest.raises(ValidationError):
        GroverNode(
            id="g-err", 
            type="grover", 
            numQubits=2, 
            truthTable="101", # 3 bits instead of 4
            numIterations=1
        )

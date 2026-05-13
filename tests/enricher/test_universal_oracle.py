import pytest
from app.enricher import Constraints
from app.enricher.universal_oracles import UniversalOracleEnricherStrategy
from app.model.CompileRequest import UniversalOracleNode
from app.openqasm3.printer import leqo_dumps
from pydantic import ValidationError

@pytest.mark.asyncio
async def test_universal_oracle_phase_mode():
    # Phase mode marking index 1 (|01>)
    node = UniversalOracleNode(
        id="uo-1", type="universal-oracle", numQubits=2, 
        targetStates=[1], mode="phase"
    )
    strategy = UniversalOracleEnricherStrategy()
    results = strategy._enrich_impl(node, Constraints(requested_inputs={}))
    
    qasm = leqo_dumps(results[0].enriched_node.implementation)
    
    expected_qasm = (
        '@leqo.input 0\n'
        'qubit[2] query;\n'
        'x query[0];\n'
        'h query[1];\n'
        'mcx query[0], query[1];\n'
        'h query[1];\n'
        'x query[0];\n'
        '@leqo.output 0\n'
        'let out = query;'
    )
    assert expected_qasm in qasm

@pytest.mark.asyncio
async def test_universal_oracle_boolean_mode():
    # Boolean mode marking index 0 (|00>)
    node = UniversalOracleNode(
        id="uo-2", type="universal-oracle", numQubits=2, 
        targetStates=[0], mode="boolean"
    )
    strategy = UniversalOracleEnricherStrategy()
    results = strategy._enrich_impl(node, Constraints(requested_inputs={}))
    
    qasm = leqo_dumps(results[0].enriched_node.implementation)
    
    expected_qasm = (
        '@leqo.input 0\n'
        'qubit[2] query;\n'
        'qubit[1] target;\n'
        'x query[0];\n'
        'x query[1];\n'
        'mcx query[0], query[1], target[0];\n'
        'x query[0];\n'
        'x query[1];\n'
        '@leqo.output 0\n'
        'let out = query;'
    )
    assert expected_qasm in qasm

def test_universal_oracle_validation_error():
    # Target state 5 is out of bounds for 2 qubits (max is 3)
    with pytest.raises(ValidationError):
        UniversalOracleNode(
            id="uo-err", type="universal-oracle", numQubits=2, 
            targetStates=[5], mode="phase"
        )

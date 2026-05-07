import pytest
from app.enricher import Constraints
from app.enricher.deutsch_jozsa import DeutschJozsaEnricherStrategy
from app.model.CompileRequest import DeutschJozsaNode
from app.openqasm3.printer import leqo_dumps

@pytest.mark.asyncio
async def test_dj_constant_zero():
    node = DeutschJozsaNode(
        id="dj-1", type="deutsch-jozsa", numQubits=2, 
        oracleType="constant", constantValue=0
    )
    strategy = DeutschJozsaEnricherStrategy()
    results = strategy._enrich_impl(node, Constraints(requested_inputs={}))
    
    qasm = leqo_dumps(results[0].enriched_node.implementation)
    
    # Assert exact QASM structure for Constant 0 (No CNOTs)
    expected_qasm = (
        'qubit[2] query;\n'
        'qubit[1] target;\n'
        'x target[0];\n'
        'h target[0];\n'
        'h query[0];\n'
        'h query[1];\n'
        'h query[0];\n'
        'h query[1];\n'
        '@leqo.output 0\n'
        'let out = query;'
    )
    assert expected_qasm in qasm

@pytest.mark.asyncio
async def test_dj_balanced():
    node = DeutschJozsaNode(
        id="dj-2", type="deutsch-jozsa", numQubits=2, 
        oracleType="balanced", balancedMask=2 # Binary 10
    )
    strategy = DeutschJozsaEnricherStrategy()
    results = strategy._enrich_impl(node, Constraints(requested_inputs={}))
    
    qasm = leqo_dumps(results[0].enriched_node.implementation)
    
    # Assert exact QASM structure for Balanced (Mask=2 means cx on query[1])
    expected_qasm = (
        'qubit[2] query;\n'
        'qubit[1] target;\n'
        'x target[0];\n'
        'h target[0];\n'
        'h query[0];\n'
        'h query[1];\n'
        'cx query[1], target[0];\n'
        'h query[0];\n'
        'h query[1];\n'
        '@leqo.output 0\n'
        'let out = query;'
    )
    assert expected_qasm in qasm

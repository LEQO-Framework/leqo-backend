import pytest

from app.enricher import Constraints
from app.enricher.universal_oracles import GroverDiffuserEnricherStrategy
from app.model.CompileRequest import GroverDiffuserNode
from app.openqasm3.printer import leqo_dumps


@pytest.mark.asyncio
async def test_grover_diffuser():
    node = GroverDiffuserNode(id="gd-1", type="grover-diffuser", numQubits=2)
    strategy = GroverDiffuserEnricherStrategy()
    results = strategy._enrich_impl(node, Constraints(requested_inputs={}))

    qasm = leqo_dumps(results[0].enriched_node.implementation)

    # Expected Grover Diffuser structure for 2 Qubits
    expected_qasm = (
        "qubit[2] query;\n"
        "h query[0];\n"
        "h query[1];\n"
        "x query[0];\n"
        "x query[1];\n"
        "h query[1];\n"
        "mcx query[0], query[1];\n"
        "h query[1];\n"
        "x query[0];\n"
        "x query[1];\n"
        "h query[0];\n"
        "h query[1];\n"
        "@leqo.output 0\n"
        "let out = query;"
    )
    assert expected_qasm in qasm

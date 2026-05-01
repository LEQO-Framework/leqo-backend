from app.enricher import Constraints
from app.enricher.gates import GateEnricherStrategy
from app.model.CompileRequest import ParameterizedGateNode
from app.model.data_types import QubitType
from tests.enricher.utils import assert_enrichment


def test_p_gate_is_mapped_to_qasm() -> None:
    node = ParameterizedGateNode(id="nodeId", gate="p", parameter=0.1)
    constraints = Constraints(
        requested_inputs={0: QubitType(3)},
        optimizeWidth=False,
        optimizeDepth=False,
    )

    result = (
        GateEnricherStrategy()
        ._enrich_parameterized_gate(node, constraints)
        .enriched_node
    )

    assert_enrichment(
        result,
        "nodeId",
        """\
        OPENQASM 3.1;
        include "stdgates.inc";
        @leqo.input 0
        qubit[3] q0;
        p(0.1) q0;
        @leqo.output 0
        let q0_out = q0;
        """,
    )

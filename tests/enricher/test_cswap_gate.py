from app.enricher import Constraints
from app.enricher.gates import GateEnricherStrategy
from app.model.CompileRequest import GateNode
from app.model.data_types import QubitType
from tests.enricher.utils import assert_enrichment


def test_cswap_gate_is_mapped_to_qasm() -> None:
    node = GateNode(id="nodeId", gate="cswap")
    constraints = Constraints(
        requested_inputs={0: QubitType(3), 1: QubitType(3), 2: QubitType(3)},
        optimizeWidth=False,
        optimizeDepth=False,
    )

    result = GateEnricherStrategy()._enrich_simple_gate(node, constraints).enriched_node

    assert_enrichment(
        result,
        "nodeId",
        """\
        OPENQASM 3.1;
        include "stdgates.inc";
        @leqo.input 0
        qubit[3] q0;
        @leqo.input 1
        qubit[3] q1;
        @leqo.input 2
        qubit[3] q2;
        cswap q0, q1, q2;
        @leqo.output 0
        let q0_out = q0;
        @leqo.output 1
        let q1_out = q1;
        @leqo.output 2
        let q2_out = q2;
        """,
    )

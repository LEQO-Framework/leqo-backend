import pytest

from app.enricher import Constraints
from app.enricher.gates import GateEnricherStrategy
from app.model.CompileRequest import ParameterizedGateNode
from app.model.data_types import IntType, QubitType
from app.model.exceptions import InputCountMismatch, InputTypeMismatch
from tests.enricher.utils import assert_enrichment


def test_cp_gate_is_mapped_to_qasm() -> None:
    node = ParameterizedGateNode(id="nodeId", gate="cp", parameter=0.1)
    constraints = Constraints(
        requested_inputs={0: QubitType(3), 1: QubitType(3)},
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
        @leqo.input 1
        qubit[3] q1;
        cp(0.1) q0, q1;
        @leqo.output 0
        let q0_out = q0;
        @leqo.output 1
        let q1_out = q1;
        """,
    )


def test_cp_gate_requires_two_qubit_inputs() -> None:
    node = ParameterizedGateNode(id="nodeId", gate="cp", parameter=0.1)
    constraints = Constraints(
        requested_inputs={0: QubitType(3)},
        optimizeWidth=False,
        optimizeDepth=False,
    )

    with pytest.raises(
        InputCountMismatch,
        match=r"^Node should have 2 inputs\. Got 1\.$",
    ):
        GateEnricherStrategy()._enrich_parameterized_gate(node, constraints)


def test_cp_gate_rejects_non_qubit_input() -> None:
    node = ParameterizedGateNode(id="nodeId", gate="cp", parameter=0.1)
    constraints = Constraints(
        requested_inputs={0: QubitType(3), 1: IntType(32)},
        optimizeWidth=False,
        optimizeDepth=False,
    )

    with pytest.raises(InputTypeMismatch):
        GateEnricherStrategy()._enrich_parameterized_gate(node, constraints)

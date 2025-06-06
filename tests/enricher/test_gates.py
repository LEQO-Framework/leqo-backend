import pytest

from app.enricher import (
    Constraints,
    ConstraintValidationException,
)
from app.enricher.gates import enrich_gate
from app.model.CompileRequest import GateNode
from app.model.data_types import IntType, QubitType
from tests.enricher.utils import assert_enrichment


def test_gate_impl_single_input() -> None:
    node = GateNode(id="nodeId", gate="h")
    constraints = Constraints(
        requested_inputs={0: QubitType(3)}, optimizeWidth=False, optimizeDepth=False
    )

    result = enrich_gate(node, constraints, gate_name="x", input_count=1).enriched_node

    assert_enrichment(
        result,
        "nodeId",
        """\
        OPENQASM 3.1;
        include "stdgates.inc";
        @leqo.input 0
        qubit[3] q0;
        x q0;
        @leqo.output 0
        let q0_out = q0;
        """,
    )


def test_gate_impl_multiple_inputs() -> None:
    node = GateNode(id="nodeId", gate="h")
    constraints = Constraints(
        requested_inputs={1: QubitType(3), 0: QubitType(3), 2: QubitType(3)},
        optimizeWidth=False,
        optimizeDepth=False,
    )

    result = enrich_gate(
        node, constraints, gate_name="ccx", input_count=3
    ).enriched_node

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
        ccx q0, q1, q2;
        @leqo.output 0
        let q0_out = q0;
        @leqo.output 1
        let q1_out = q1;
        @leqo.output 2
        let q2_out = q2;
        """,
    )


def test_gate_impl_wrong_input_count() -> None:
    node = GateNode(id="nodeId", gate="h")
    constraints = Constraints(
        requested_inputs={0: QubitType(3)},
        optimizeWidth=False,
        optimizeDepth=False,
    )

    with pytest.raises(
        ConstraintValidationException, match="^Gate 'abc' requires 3 qubits$"
    ):
        enrich_gate(node, constraints=None, gate_name="abc", input_count=3)

    with pytest.raises(
        ConstraintValidationException, match="^Gate 'abc' requires 3 qubits$"
    ):
        enrich_gate(node, constraints, gate_name="abc", input_count=3)


def test_gate_impl_size_mismatch() -> None:
    node = GateNode(id="nodeId", gate="h")
    constraints = Constraints(
        requested_inputs={1: QubitType(2), 0: QubitType(3), 2: QubitType(42)},
        optimizeWidth=False,
        optimizeDepth=False,
    )

    with pytest.raises(
        ConstraintValidationException, match="^Gate inputs must be of equal size$"
    ):
        enrich_gate(node, constraints, gate_name="abc", input_count=3)


def test_gate_impl_type_mismatch() -> None:
    node = GateNode(id="nodeId", gate="h")
    constraints = Constraints(
        requested_inputs={1: QubitType(2), 0: IntType(32)},
        optimizeWidth=False,
        optimizeDepth=False,
    )

    with pytest.raises(
        ConstraintValidationException, match="^Gate may only have qubit inputs$"
    ):
        enrich_gate(node, constraints, gate_name="abc", input_count=2)

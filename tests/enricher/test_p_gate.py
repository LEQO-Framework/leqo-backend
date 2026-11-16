import pytest

from app.enricher import Constraints
from app.enricher.gates import GateEnricherStrategy
from app.model.CompileRequest import ParameterizedGateNode
from app.model.data_types import IntType, QubitType
from app.model.exceptions import InputCountMismatch, InputTypeMismatch
from tests.enricher.utils import assert_enrichment


@pytest.mark.parametrize(
    "parameter",
    [
        0.1,
        0.0,
        -0.1,
    ],
)
def test_p_gate_is_mapped_to_qasm(parameter: float) -> None:
    node = ParameterizedGateNode(id="nodeId", gate="p", parameter=parameter)
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
        f"""\
        OPENQASM 3.1;
        include "stdgates.inc";
        @leqo.input 0
        qubit[3] q0;
        p({parameter}) q0;
        @leqo.output 0
        let q0_out = q0;
        """,
    )


@pytest.mark.parametrize(
    ("requested_inputs", "expected_actual_count"),
    [
        ({}, 0),
        ({0: QubitType(3), 1: QubitType(3)}, 2),
    ],
)
def test_p_gate_requires_exactly_one_input(
    requested_inputs: dict[int, QubitType],
    expected_actual_count: int,
) -> None:
    node = ParameterizedGateNode(id="nodeId", gate="p", parameter=0.1)
    constraints = Constraints(
        requested_inputs=requested_inputs,
        optimizeWidth=False,
        optimizeDepth=False,
    )

    with pytest.raises(
        InputCountMismatch,
        match=rf"^Node should have 1 inputs\. Got {expected_actual_count}\.$",
    ):
        GateEnricherStrategy()._enrich_parameterized_gate(node, constraints)


def test_p_gate_rejects_non_qubit_input() -> None:
    node = ParameterizedGateNode(id="nodeId", gate="p", parameter=0.1)
    constraints = Constraints(
        requested_inputs={0: IntType(32)},
        optimizeWidth=False,
        optimizeDepth=False,
    )

    with pytest.raises(
        InputTypeMismatch,
        match=r"^Expected type 'qubit' for input 0\.",
    ):
        GateEnricherStrategy()._enrich_parameterized_gate(node, constraints)

import pytest

from app.enricher import Constraints
from app.enricher.gates import GateEnricherStrategy, enrich_gate
from app.model.CompileRequest import GateNode, ParameterizedGateNode
from app.model.data_types import IntType, QubitType
from app.model.exceptions import (
    InputCountMismatch,
    InputSizeMismatch,
    InputTypeMismatch,
)
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
        InputCountMismatch, match=r"^Node should have 3 inputs. Got 0.$"
    ):
        enrich_gate(node, constraints=None, gate_name="abc", input_count=3)

    with pytest.raises(
        InputCountMismatch, match=r"^Node should have 3 inputs\. Got 1\.$"
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
        InputSizeMismatch, match=r"^Expected size 2 for input 0\. Got 3\.$"
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
        InputTypeMismatch,
        match=r"^Expected type 'qubit' for input 0\. Got 'IntType\(size=32\)'\.$",
    ):
        enrich_gate(node, constraints, gate_name="abc", input_count=2)


@pytest.mark.parametrize(
    "gate_name",
    ["s", "sdg", "sx", "tdg"],
)
def test_supported_single_qubit_lcm_gates_are_mapped_to_qasm(
    gate_name: str,
) -> None:
    node = GateNode(id="nodeId", gate=gate_name)
    constraints = Constraints(
        requested_inputs={0: QubitType(3)},
        optimizeWidth=False,
        optimizeDepth=False,
    )

    result = GateEnricherStrategy()._enrich_simple_gate(node, constraints).enriched_node

    assert_enrichment(
        result,
        "nodeId",
        f"""\
        OPENQASM 3.1;
        include "stdgates.inc";
        @leqo.input 0
        qubit[3] q0;
        {gate_name} q0;
        @leqo.output 0
        let q0_out = q0;
        """,
    )


@pytest.mark.parametrize(
    "gate_name",
    ["swap", "cy", "cz", "ch"],
)
def test_supported_two_qubit_lcm_gates_are_mapped_to_qasm(
    gate_name: str,
) -> None:
    node = GateNode(id="nodeId", gate=gate_name)
    constraints = Constraints(
        requested_inputs={0: QubitType(3), 1: QubitType(3)},
        optimizeWidth=False,
        optimizeDepth=False,
    )

    result = GateEnricherStrategy()._enrich_simple_gate(node, constraints).enriched_node

    assert_enrichment(
        result,
        "nodeId",
        f"""\
        OPENQASM 3.1;
        include "stdgates.inc";
        @leqo.input 0
        qubit[3] q0;
        @leqo.input 1
        qubit[3] q1;
        {gate_name} q0, q1;
        @leqo.output 0
        let q0_out = q0;
        @leqo.output 1
        let q1_out = q1;
        """,
    )


@pytest.mark.parametrize(
    ("gate_name", "parameter"),
    [
        ("crx", 0.1),
        ("cry", 0.2),
        ("crz", 0.3),
    ],
)
def test_supported_controlled_rotation_lcm_gates_are_mapped_to_qasm(
    gate_name: str,
    parameter: float,
) -> None:
    node = ParameterizedGateNode(
        id="nodeId",
        gate=gate_name,
        parameter=parameter,
    )
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
        f"""\
        OPENQASM 3.1;
        include "stdgates.inc";
        @leqo.input 0
        qubit[3] q0;
        @leqo.input 1
        qubit[3] q1;
        {gate_name}({parameter}) q0, q1;
        @leqo.output 0
        let q0_out = q0;
        @leqo.output 1
        let q1_out = q1;
        """,
    )


def test_controlled_single_qubit_gate_is_mapped_to_qasm() -> None:
    node = GateNode(id="nodeId", gate="x", controlCount=1)
    constraints = Constraints(
        requested_inputs={0: QubitType(3), 1: QubitType(3)},
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
        ctrl @ x q0, q1;
        @leqo.output 0
        let q0_out = q0;
        @leqo.output 1
        let q1_out = q1;
        """,
    )


def test_multi_controlled_single_qubit_gate_is_mapped_to_qasm() -> None:
    node = GateNode(id="nodeId", gate="x", controlCount=2)
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
        ctrl(2) @ x q0, q1, q2;
        @leqo.output 0
        let q0_out = q0;
        @leqo.output 1
        let q1_out = q1;
        @leqo.output 2
        let q2_out = q2;
        """,
    )


def test_controlled_parameterized_gate_is_mapped_to_qasm() -> None:
    node = ParameterizedGateNode(
        id="nodeId",
        gate="rx",
        parameter=0.5,
        controlCount=1,
    )
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
        ctrl @ rx(0.5) q0, q1;
        @leqo.output 0
        let q0_out = q0;
        @leqo.output 1
        let q1_out = q1;
        """,
    )

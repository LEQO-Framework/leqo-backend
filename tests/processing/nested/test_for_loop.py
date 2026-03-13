import pytest

from app.model.CompileRequest import (
    Edge,
    GateNode,
    ImplementationNode,
    NestedBlock,
    ForNode,
)
from app.model.data_types import (
    LeqoSupportedType,
    QubitType,
)
from app.openqasm3.printer import leqo_dumps
from app.transformation_manager.nested.for_loop import enrich_for_loop
from app.transformation_manager.utils import normalize_qasm_string
from tests.processing.nested.utils import H_IMPL, X_IMPL, build_graph


async def assert_for_loop_enrichment(
    node: ForNode,
    requested_inputs: dict[int, LeqoSupportedType],
    frontend_name_to_index: dict[str, int],
    expected: str,
) -> None:
    enriched_node = await enrich_for_loop(
        node, requested_inputs, frontend_name_to_index, build_graph
    )
    impl = leqo_dumps(enriched_node.implementation)
    print(impl)
    assert normalize_qasm_string(expected) == normalize_qasm_string(impl)


@pytest.mark.asyncio
async def test_basic_for() -> None:
    """Test a basic for loop with a single qubit input."""
    await assert_for_loop_enrichment(
        ForNode(
            id="for-node",
            iterator="i",
            range_start=0,
            range_end=10,
            step=1,
            block=NestedBlock(
                nodes=[ImplementationNode(id="h-node", implementation=H_IMPL)],
                edges=[
                    Edge(source=("h-node", 0), target=("for-node", 0)),
                    Edge(source=("for-node", 0), target=("h-node", 0)),
                ],
            ),
        ),
        requested_inputs={0: QubitType(1)},
        frontend_name_to_index={},
        expected="""\
        OPENQASM 3.1;
        @leqo.input 0
        qubit[1] leqo_f64998ea82305902a81934e9ecfd5c79_pass_node_declaration_0;
        let leqo_f64998ea82305902a81934e9ecfd5c79_pass_node_alias_0 = leqo_f64998ea82305902a81934e9ecfd5c79_pass_node_declaration_0;
        let leqo_f64998ea82305902a81934e9ecfd5c79_loop_reg = leqo_f64998ea82305902a81934e9ecfd5c79_pass_node_declaration_0;
        for int i in [0:10] {
          let leqo_0f22e31da1be57ea8479533ced7f8788_q = leqo_f64998ea82305902a81934e9ecfd5c79_loop_reg[{0}];
          h leqo_0f22e31da1be57ea8479533ced7f8788_q;
          let leqo_0f22e31da1be57ea8479533ced7f8788__out = leqo_0f22e31da1be57ea8479533ced7f8788_q;
        }
        let leqo_893e8683ef9b5dd2b94529d9388a2dc1_pass_node_declaration_0 = leqo_f64998ea82305902a81934e9ecfd5c79_loop_reg[{0}];
        @leqo.output 0
        let leqo_893e8683ef9b5dd2b94529d9388a2dc1_pass_node_alias_0 = leqo_893e8683ef9b5dd2b94529d9388a2dc1_pass_node_declaration_0;
        """,
    )


@pytest.mark.asyncio
async def test_for_custom_step() -> None:
    """Test a for loop with a non-default step size."""
    await assert_for_loop_enrichment(
        ForNode(
            id="for-node",
            iterator="j",
            range_start=0,
            range_end=20,
            step=3,
            block=NestedBlock(
                nodes=[ImplementationNode(id="x-node", implementation=X_IMPL)],
                edges=[
                    Edge(source=("x-node", 0), target=("for-node", 0)),
                    Edge(source=("for-node", 0), target=("x-node", 0)),
                ],
            ),
        ),
        requested_inputs={0: QubitType(1)},
        frontend_name_to_index={},
        expected="""\
        OPENQASM 3.1;
        @leqo.input 0
        qubit[1] leqo_f64998ea82305902a81934e9ecfd5c79_pass_node_declaration_0;
        let leqo_f64998ea82305902a81934e9ecfd5c79_pass_node_alias_0 = leqo_f64998ea82305902a81934e9ecfd5c79_pass_node_declaration_0;
        let leqo_f64998ea82305902a81934e9ecfd5c79_loop_reg = leqo_f64998ea82305902a81934e9ecfd5c79_pass_node_declaration_0;
        for int j in [0:3:20] {
          let leqo_40da8ad6eead5c82b58a503771301f03_q = leqo_f64998ea82305902a81934e9ecfd5c79_loop_reg[{0}];
          x leqo_40da8ad6eead5c82b58a503771301f03_q;
          let leqo_40da8ad6eead5c82b58a503771301f03__out = leqo_40da8ad6eead5c82b58a503771301f03_q;
        }
        let leqo_893e8683ef9b5dd2b94529d9388a2dc1_pass_node_declaration_0 = leqo_f64998ea82305902a81934e9ecfd5c79_loop_reg[{0}];
        @leqo.output 0
        let leqo_893e8683ef9b5dd2b94529d9388a2dc1_pass_node_alias_0 = leqo_893e8683ef9b5dd2b94529d9388a2dc1_pass_node_declaration_0;
        """,
    )


@pytest.mark.asyncio
async def test_for_multi_qubit() -> None:
    """Test a for loop with multiple qubit inputs and gate nodes."""
    await assert_for_loop_enrichment(
        ForNode(
            id="for-node",
            iterator="k",
            range_start=1,
            range_end=5,
            step=1,
            block=NestedBlock(
                nodes=[
                    GateNode(id="h-node", gate="h"),
                    GateNode(id="cx-node", gate="cx"),
                ],
                edges=[
                    Edge(source=("for-node", 0), target=("h-node", 0)),
                    Edge(source=("for-node", 1), target=("cx-node", 0)),
                    Edge(source=("h-node", 0), target=("cx-node", 1)),
                    Edge(source=("cx-node", 0), target=("for-node", 1)),
                    Edge(source=("cx-node", 1), target=("for-node", 0)),
                ],
            ),
        ),
        requested_inputs={0: QubitType(1), 1: QubitType(1)},
        frontend_name_to_index={},
        expected="""\
        OPENQASM 3.1;
        include "stdgates.inc";
        @leqo.input 0
        qubit[1] leqo_f64998ea82305902a81934e9ecfd5c79_pass_node_declaration_0;
        let leqo_f64998ea82305902a81934e9ecfd5c79_pass_node_alias_0 = leqo_f64998ea82305902a81934e9ecfd5c79_pass_node_declaration_0;
        @leqo.input 1
        qubit[1] leqo_f64998ea82305902a81934e9ecfd5c79_pass_node_declaration_1;
        let leqo_f64998ea82305902a81934e9ecfd5c79_pass_node_alias_1 = leqo_f64998ea82305902a81934e9ecfd5c79_pass_node_declaration_1;
        let leqo_f64998ea82305902a81934e9ecfd5c79_loop_reg = leqo_f64998ea82305902a81934e9ecfd5c79_pass_node_declaration_0 ++ leqo_f64998ea82305902a81934e9ecfd5c79_pass_node_declaration_1;
        for int k in [1:5] {
          let leqo_0f22e31da1be57ea8479533ced7f8788_q0 = leqo_f64998ea82305902a81934e9ecfd5c79_loop_reg[{0}];
          h leqo_0f22e31da1be57ea8479533ced7f8788_q0;
          let leqo_0f22e31da1be57ea8479533ced7f8788_q0_out = leqo_0f22e31da1be57ea8479533ced7f8788_q0;
          let leqo_a0e038f8360a54fe962f8d87eb01051a_q0 = leqo_f64998ea82305902a81934e9ecfd5c79_loop_reg[{1}];
          let leqo_a0e038f8360a54fe962f8d87eb01051a_q1 = leqo_f64998ea82305902a81934e9ecfd5c79_loop_reg[{0}];
          cx leqo_a0e038f8360a54fe962f8d87eb01051a_q0, leqo_a0e038f8360a54fe962f8d87eb01051a_q1;
          let leqo_a0e038f8360a54fe962f8d87eb01051a_q0_out = leqo_a0e038f8360a54fe962f8d87eb01051a_q0;
          let leqo_a0e038f8360a54fe962f8d87eb01051a_q1_out = leqo_a0e038f8360a54fe962f8d87eb01051a_q1;
        }
        let leqo_893e8683ef9b5dd2b94529d9388a2dc1_pass_node_declaration_0 = leqo_f64998ea82305902a81934e9ecfd5c79_loop_reg[{0}];
        @leqo.output 0
        let leqo_893e8683ef9b5dd2b94529d9388a2dc1_pass_node_alias_0 = leqo_893e8683ef9b5dd2b94529d9388a2dc1_pass_node_declaration_0;
        let leqo_893e8683ef9b5dd2b94529d9388a2dc1_pass_node_declaration_1 = leqo_f64998ea82305902a81934e9ecfd5c79_loop_reg[{1}];
        @leqo.output 1
        let leqo_893e8683ef9b5dd2b94529d9388a2dc1_pass_node_alias_1 = leqo_893e8683ef9b5dd2b94529d9388a2dc1_pass_node_declaration_1;
        """,
    )


@pytest.mark.asyncio
async def test_for_negative_range() -> None:
    """Test a for loop with a negative start range."""
    await assert_for_loop_enrichment(
        ForNode(
            id="for-node",
            iterator="n",
            range_start=-5,
            range_end=5,
            step=2,
            block=NestedBlock(
                nodes=[ImplementationNode(id="h-node", implementation=H_IMPL)],
                edges=[
                    Edge(source=("h-node", 0), target=("for-node", 0)),
                    Edge(source=("for-node", 0), target=("h-node", 0)),
                ],
            ),
        ),
        requested_inputs={0: QubitType(1)},
        frontend_name_to_index={},
        expected="""\
        OPENQASM 3.1;
        @leqo.input 0
        qubit[1] leqo_f64998ea82305902a81934e9ecfd5c79_pass_node_declaration_0;
        let leqo_f64998ea82305902a81934e9ecfd5c79_pass_node_alias_0 = leqo_f64998ea82305902a81934e9ecfd5c79_pass_node_declaration_0;
        let leqo_f64998ea82305902a81934e9ecfd5c79_loop_reg = leqo_f64998ea82305902a81934e9ecfd5c79_pass_node_declaration_0;
        for int n in [-5:2:5] {
          let leqo_0f22e31da1be57ea8479533ced7f8788_q = leqo_f64998ea82305902a81934e9ecfd5c79_loop_reg[{0}];
          h leqo_0f22e31da1be57ea8479533ced7f8788_q;
          let leqo_0f22e31da1be57ea8479533ced7f8788__out = leqo_0f22e31da1be57ea8479533ced7f8788_q;
        }
        let leqo_893e8683ef9b5dd2b94529d9388a2dc1_pass_node_declaration_0 = leqo_f64998ea82305902a81934e9ecfd5c79_loop_reg[{0}];
        @leqo.output 0
        let leqo_893e8683ef9b5dd2b94529d9388a2dc1_pass_node_alias_0 = leqo_893e8683ef9b5dd2b94529d9388a2dc1_pass_node_declaration_0;
        """,
    )
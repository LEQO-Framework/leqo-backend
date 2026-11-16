import pytest

from app.model.CompileRequest import (
    Edge,
    GateNode,
    ImplementationNode,
    NestedBlock,
    WhileNode,
)
from app.model.data_types import (
    BitType,
    IntType,
    LeqoSupportedType,
    QubitType,
)
from app.openqasm3.printer import leqo_dumps
from app.transformation_manager.nested.while_loop import enrich_while_loop
from app.transformation_manager.utils import normalize_qasm_string
from tests.processing.nested.utils import H_IMPL, X_IMPL, build_graph


async def assert_while_loop_enrichment(
    node: WhileNode,
    requested_inputs: dict[int, LeqoSupportedType],
    frontend_name_to_index: dict[str, int],
    expected: str,
) -> None:
    enriched_node = await enrich_while_loop(
        node, requested_inputs, frontend_name_to_index, build_graph
    )
    impl = leqo_dumps(enriched_node.implementation)
    print(impl)
    assert normalize_qasm_string(expected) == normalize_qasm_string(impl)


@pytest.mark.asyncio
async def test_basic_while() -> None:
    """Test a simple while loop with a single condition variable and one qubit."""
    await assert_while_loop_enrichment(
        WhileNode(
            id="while-node",
            condition="i < 5",
            block=NestedBlock(
                nodes=[ImplementationNode(id="x-node", implementation=X_IMPL)],
                edges=[
                    Edge(source=("x-node", 0), target=("while-node", 1)),
                    Edge(source=("while-node", 1), target=("x-node", 0)),
                ],
            ),
        ),
        requested_inputs={0: IntType(32), 1: QubitType(1)},
        frontend_name_to_index={"i": 0},
        expected="""\
        OPENQASM 3.1;
        @leqo.input 0
        int[32] leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_0;
        let leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_alias_0 = leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_0;
        @leqo.input 1
        qubit[1] leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_1;
        let leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_alias_1 = leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_1;
        let leqo_7b8143e0b0a65b73992d570b848c7838_loop_reg = leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_1;
        while (leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_0 < 5) {
          let leqo_40da8ad6eead5c82b58a503771301f03_q = leqo_7b8143e0b0a65b73992d570b848c7838_loop_reg[{0}];
          x leqo_40da8ad6eead5c82b58a503771301f03_q;
          let leqo_40da8ad6eead5c82b58a503771301f03__out = leqo_40da8ad6eead5c82b58a503771301f03_q;
        }
        int[32] leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_declaration_0;
        @leqo.output 0
        let leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_alias_0 = leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_declaration_0;
        let leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_declaration_1 = leqo_7b8143e0b0a65b73992d570b848c7838_loop_reg[{0}];
        @leqo.output 1
        let leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_alias_1 = leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_declaration_1;
        """,
    )


@pytest.mark.asyncio
async def test_complex_condition_while() -> None:
    """Test a while loop with a complex multi-variable condition."""
    await assert_while_loop_enrichment(
        WhileNode(
            id="while-node",
            condition="a < 10 && (b > 0 || c != 3)",
            block=NestedBlock(
                nodes=[ImplementationNode(id="h-node", implementation=H_IMPL)],
                edges=[
                    Edge(source=("h-node", 0), target=("while-node", 3)),
                    Edge(source=("while-node", 3), target=("h-node", 0)),
                ],
            ),
        ),
        requested_inputs={
            0: IntType(32),
            1: IntType(32),
            2: IntType(32),
            3: QubitType(1),
        },
        frontend_name_to_index={"a": 0, "b": 1, "c": 2},
        expected="""\
        OPENQASM 3.1;
        @leqo.input 0
        int[32] leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_0;
        let leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_alias_0 = leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_0;
        @leqo.input 1
        int[32] leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_1;
        let leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_alias_1 = leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_1;
        @leqo.input 2
        int[32] leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_2;
        let leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_alias_2 = leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_2;
        @leqo.input 3
        qubit[1] leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_3;
        let leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_alias_3 = leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_3;
        let leqo_7b8143e0b0a65b73992d570b848c7838_loop_reg = leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_3;
        while (leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_0 < 10 && (leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_1 > 0 || leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_2 != 3)) {
          let leqo_0f22e31da1be57ea8479533ced7f8788_q = leqo_7b8143e0b0a65b73992d570b848c7838_loop_reg[{0}];
          h leqo_0f22e31da1be57ea8479533ced7f8788_q;
          let leqo_0f22e31da1be57ea8479533ced7f8788__out = leqo_0f22e31da1be57ea8479533ced7f8788_q;
        }
        int[32] leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_declaration_0;
        @leqo.output 0
        let leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_alias_0 = leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_declaration_0;
        int[32] leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_declaration_1;
        @leqo.output 1
        let leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_alias_1 = leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_declaration_1;
        int[32] leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_declaration_2;
        @leqo.output 2
        let leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_alias_2 = leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_declaration_2;
        let leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_declaration_3 = leqo_7b8143e0b0a65b73992d570b848c7838_loop_reg[{0}];
        @leqo.output 3
        let leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_alias_3 = leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_declaration_3;
        """,
    )


@pytest.mark.asyncio
async def test_while_multi_node_body() -> None:
    """Test a while loop with multiple gate nodes in its body."""
    await assert_while_loop_enrichment(
        WhileNode(
            id="while-node",
            condition="i < 3",
            block=NestedBlock(
                nodes=[
                    GateNode(id="h-node", gate="h"),
                    GateNode(id="cx-node", gate="cx"),
                ],
                edges=[
                    Edge(source=("while-node", 1), target=("h-node", 0)),
                    Edge(source=("while-node", 2), target=("cx-node", 0)),
                    Edge(source=("h-node", 0), target=("cx-node", 1)),
                    Edge(source=("cx-node", 0), target=("while-node", 2)),
                    Edge(source=("cx-node", 1), target=("while-node", 1)),
                ],
            ),
        ),
        requested_inputs={0: IntType(32), 1: QubitType(1), 2: QubitType(1)},
        frontend_name_to_index={"i": 0},
        expected="""\
        OPENQASM 3.1;
        include "stdgates.inc";
        @leqo.input 0
        int[32] leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_0;
        let leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_alias_0 = leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_0;
        @leqo.input 1
        qubit[1] leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_1;
        let leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_alias_1 = leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_1;
        @leqo.input 2
        qubit[1] leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_2;
        let leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_alias_2 = leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_2;
        let leqo_7b8143e0b0a65b73992d570b848c7838_loop_reg = leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_1 ++ leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_2;
        while (leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_0 < 3) {
          let leqo_0f22e31da1be57ea8479533ced7f8788_q0 = leqo_7b8143e0b0a65b73992d570b848c7838_loop_reg[{0}];
          h leqo_0f22e31da1be57ea8479533ced7f8788_q0;
          let leqo_0f22e31da1be57ea8479533ced7f8788_q0_out = leqo_0f22e31da1be57ea8479533ced7f8788_q0;
          let leqo_a0e038f8360a54fe962f8d87eb01051a_q0 = leqo_7b8143e0b0a65b73992d570b848c7838_loop_reg[{1}];
          let leqo_a0e038f8360a54fe962f8d87eb01051a_q1 = leqo_7b8143e0b0a65b73992d570b848c7838_loop_reg[{0}];
          cx leqo_a0e038f8360a54fe962f8d87eb01051a_q0, leqo_a0e038f8360a54fe962f8d87eb01051a_q1;
          let leqo_a0e038f8360a54fe962f8d87eb01051a_q0_out = leqo_a0e038f8360a54fe962f8d87eb01051a_q0;
          let leqo_a0e038f8360a54fe962f8d87eb01051a_q1_out = leqo_a0e038f8360a54fe962f8d87eb01051a_q1;
        }
        int[32] leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_declaration_0;
        @leqo.output 0
        let leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_alias_0 = leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_declaration_0;
        let leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_declaration_1 = leqo_7b8143e0b0a65b73992d570b848c7838_loop_reg[{0}];
        @leqo.output 1
        let leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_alias_1 = leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_declaration_1;
        let leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_declaration_2 = leqo_7b8143e0b0a65b73992d570b848c7838_loop_reg[{1}];
        @leqo.output 2
        let leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_alias_2 = leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_declaration_2;
        """,
    )


@pytest.mark.asyncio
async def test_while_bit_condition() -> None:
    """Test a while loop with a bit-type condition variable."""
    await assert_while_loop_enrichment(
        WhileNode(
            id="while-node",
            condition="flag == 1",
            block=NestedBlock(
                nodes=[ImplementationNode(id="x-node", implementation=X_IMPL)],
                edges=[
                    Edge(source=("x-node", 0), target=("while-node", 1)),
                    Edge(source=("while-node", 1), target=("x-node", 0)),
                ],
            ),
        ),
        requested_inputs={0: BitType(1), 1: QubitType(1)},
        frontend_name_to_index={"flag": 0},
        expected="""\
        OPENQASM 3.1;
        @leqo.input 0
        bit[1] leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_0;
        let leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_alias_0 = leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_0;
        @leqo.input 1
        qubit[1] leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_1;
        let leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_alias_1 = leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_1;
        let leqo_7b8143e0b0a65b73992d570b848c7838_loop_reg = leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_1;
        while (leqo_7b8143e0b0a65b73992d570b848c7838_pass_node_declaration_0 == 1) {
          let leqo_40da8ad6eead5c82b58a503771301f03_q = leqo_7b8143e0b0a65b73992d570b848c7838_loop_reg[{0}];
          x leqo_40da8ad6eead5c82b58a503771301f03_q;
          let leqo_40da8ad6eead5c82b58a503771301f03__out = leqo_40da8ad6eead5c82b58a503771301f03_q;
        }
        bit[1] leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_declaration_0;
        @leqo.output 0
        let leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_alias_0 = leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_declaration_0;
        let leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_declaration_1 = leqo_7b8143e0b0a65b73992d570b848c7838_loop_reg[{0}];
        @leqo.output 1
        let leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_alias_1 = leqo_d2bd13e2358e5e23b629272de4a52899_pass_node_declaration_1;
        """,
    )

import pytest

from app.model.CompileRequest import (
    Edge,
    ImplementationNode,
    NestedBlock,
    WhileNode,
)
from app.model.data_types import (
    IntType,
    LeqoSupportedType,
    QubitType,
)
from app.openqasm3.printer import leqo_dumps
from app.transformation_manager.nested.while_loop import enrich_while_loop
from app.transformation_manager.utils import normalize_qasm_string
from tests.processing.nested.utils import X_IMPL, build_graph


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
    await assert_while_loop_enrichment(
        WhileNode(
            id="if-node",
            condition="i < 5",
            block=NestedBlock(
                nodes=[ImplementationNode(id="x-node", implementation=X_IMPL)],
                edges=[
                    Edge(source=("x-node", 0), target=("if-node", 1)),
                    Edge(source=("if-node", 1), target=("x-node", 0)),
                ],
            ),
        ),
        requested_inputs={0: IntType(32), 1: QubitType(1)},
        frontend_name_to_index={"i": 0},
        expected="""\
        OPENQASM 3.1;
        @leqo.input 0
        int[32] leqo_0f993612d9615486a55a1cd3d4158b45_pass_node_declaration_0;
        let leqo_0f993612d9615486a55a1cd3d4158b45_pass_node_alias_0 = leqo_0f993612d9615486a55a1cd3d4158b45_pass_node_declaration_0;
        @leqo.input 1
        qubit[1] leqo_0f993612d9615486a55a1cd3d4158b45_pass_node_declaration_1;
        let leqo_0f993612d9615486a55a1cd3d4158b45_pass_node_alias_1 = leqo_0f993612d9615486a55a1cd3d4158b45_pass_node_declaration_1;
        let leqo_0f993612d9615486a55a1cd3d4158b45_loop_reg = leqo_0f993612d9615486a55a1cd3d4158b45_pass_node_declaration_1;
        while (leqo_0f993612d9615486a55a1cd3d4158b45_pass_node_declaration_0 < 5) {
          let leqo_40da8ad6eead5c82b58a503771301f03_q = leqo_0f993612d9615486a55a1cd3d4158b45_loop_reg[{0}];
          x leqo_40da8ad6eead5c82b58a503771301f03_q;
          let leqo_40da8ad6eead5c82b58a503771301f03__out = leqo_40da8ad6eead5c82b58a503771301f03_q;
        }
        int[32] leqo_e8d241f16cf659c4a39a85d20102754b_pass_node_declaration_0;
        @leqo.output 0
        let leqo_e8d241f16cf659c4a39a85d20102754b_pass_node_alias_0 = leqo_e8d241f16cf659c4a39a85d20102754b_pass_node_declaration_0;
        let leqo_e8d241f16cf659c4a39a85d20102754b_pass_node_declaration_1 = leqo_0f993612d9615486a55a1cd3d4158b45_loop_reg[{0}];
        @leqo.output 1
        let leqo_e8d241f16cf659c4a39a85d20102754b_pass_node_alias_1 = leqo_e8d241f16cf659c4a39a85d20102754b_pass_node_declaration_1;
        """,
    )
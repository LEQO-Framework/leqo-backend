import pytest

from app.model.CompileRequest import (
    Edge,
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
from tests.processing.nested.utils import H_IMPL, build_graph


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
    await assert_for_loop_enrichment(
        ForNode(
            id="if-node",
            iterator="i",
            range_start=0,
            range_end=10,
            step=1,
            block=NestedBlock(
                nodes=[ImplementationNode(id="h-node", implementation=H_IMPL)],
                edges=[
                    Edge(source=("h-node", 0), target=("if-node", 0)),
                    Edge(source=("if-node", 0), target=("h-node", 0)),
                ],
            ),
        ),
        requested_inputs={0: QubitType(1)},
        frontend_name_to_index={},
        expected="""\
        OPENQASM 3.1;
        @leqo.input 0
        qubit[1] leqo_af4ab0884f0d5aa3a87cdf116e20543e_pass_node_declaration_0;
        let leqo_af4ab0884f0d5aa3a87cdf116e20543e_pass_node_alias_0 = leqo_af4ab0884f0d5aa3a87cdf116e20543e_pass_node_declaration_0;
        let leqo_af4ab0884f0d5aa3a87cdf116e20543e_loop_reg = leqo_af4ab0884f0d5aa3a87cdf116e20543e_pass_node_declaration_0;
        for int i in [0:10] {
          let leqo_0f22e31da1be57ea8479533ced7f8788_q = leqo_af4ab0884f0d5aa3a87cdf116e20543e_loop_reg[{0}];
          h leqo_0f22e31da1be57ea8479533ced7f8788_q;
          let leqo_0f22e31da1be57ea8479533ced7f8788__out = leqo_0f22e31da1be57ea8479533ced7f8788_q;
        }
        let leqo_7fa32f00e76450ae8a3f1fca36e8517a_pass_node_declaration_0 = leqo_af4ab0884f0d5aa3a87cdf116e20543e_loop_reg[{0}];
        @leqo.output 0
        let leqo_7fa32f00e76450ae8a3f1fca36e8517a_pass_node_alias_0 = leqo_7fa32f00e76450ae8a3f1fca36e8517a_pass_node_declaration_0;
        """,
    )
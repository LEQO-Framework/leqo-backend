import pytest

from app.enricher import Enricher
from app.model.CompileRequest import (
    Edge,
    IfThenElseNode,
    ImplementationNode,
    NestedBlock,
    OptimizeSettings,
)
from app.model.data_types import BitType, IntType, LeqoSupportedType, QubitType
from app.openqasm3.printer import leqo_dumps
from app.processing import CommonProcessor
from app.processing.converted_graph import ConvertedProgramGraph
from app.processing.if_else import enrich_if_else, get_pass_node_impl
from app.processing.utils import stem_qasm_string

h_impl = """
OPENQASM 3.1;
@leqo.input 0
qubit[1] q;
h q;
@leqo.output 0
let _out = q;
"""
x_impl = """
OPENQASM 3.1;
@leqo.input 0
qubit[1] q;
x q;
@leqo.output 0
let _out = q;
"""


class DummyOptimizeSettings(OptimizeSettings):
    optimizeWidth = None
    optimizeDepth = None


build_graph = CommonProcessor(
    Enricher(), ConvertedProgramGraph(), DummyOptimizeSettings()
)._build_inner_graph


async def assert_if_else_enrichment(
    node: IfThenElseNode,
    requested_inputs: dict[int, LeqoSupportedType],
    frontend_name_to_index: dict[str, int],
    expected: str,
) -> None:
    enriched_node = await enrich_if_else(
        node, requested_inputs, frontend_name_to_index, build_graph
    )
    print(stem_qasm_string(enriched_node.implementation))
    assert stem_qasm_string(expected) == stem_qasm_string(enriched_node.implementation)


def test_pass_node_impl() -> None:
    actual = get_pass_node_impl({0: QubitType(3), 1: IntType(32)})
    expected = """
        OPENQASM 3.1;
        @leqo.input 0
        qubit[3] pass_node_declaration_0;
        @leqo.output 0
        let pass_node_alias_0 = pass_node_declaration_0;
        @leqo.input 1
        int[32] pass_node_declaration_1;
        @leqo.output 1
        let pass_node_alias_1 = pass_node_declaration_1;
        """
    assert stem_qasm_string(expected) == stem_qasm_string(leqo_dumps(actual))


@pytest.mark.asyncio
async def test_basic() -> None:
    await assert_if_else_enrichment(
        IfThenElseNode(
            id="if-node",
            condition="b == 3",
            thenBlock=NestedBlock(
                nodes=[ImplementationNode(id="h-node", implementation=h_impl)],
                edges=[
                    Edge(source=("h-node", 0), target=("if-node", 1)),
                    Edge(source=("if-node", 1), target=("h-node", 0)),
                ],
            ),
            elseBlock=NestedBlock(
                nodes=[ImplementationNode(id="x-node", implementation=x_impl)],
                edges=[
                    Edge(source=("x-node", 0), target=("if-node", 1)),
                    Edge(source=("if-node", 1), target=("x-node", 0)),
                ],
            ),
        ),
        requested_inputs={0: BitType(1), 1: QubitType(1)},
        frontend_name_to_index={"b": 0},
        expected="""\
        OPENQASM 3.1;
        @leqo.input 0
        bit[1] leqo_pass_node_declaration_0;
        let leqo_pass_node_alias_0 = leqo_pass_node_declaration_0;
        @leqo.input 1
        qubit[1] leqo_pass_node_declaration_1;
        let leqo_pass_node_alias_1 = leqo_pass_node_declaration_1;
        let leqo_if_reg = leqo_pass_node_declaration_1;
        if (leqo_pass_node_declaration_0 == 3) {
          let leqo_q = leqo_if_reg[{0}];
          h leqo_q;
          let leqo__out = leqo_q;
        } else {
          let leqo_q = leqo_if_reg[{0}];
          x leqo_q;
          let leqo__out = leqo_q;
        }
        bit[1] leqo_pass_node_declaration_0;
        @leqo.output 0
        let leqo_pass_node_alias_0 = leqo_pass_node_declaration_0;
        let leqo_pass_node_declaration_1 = leqo_if_reg[{0}];
        @leqo.output 1
        let leqo_pass_node_alias_1 = leqo_pass_node_declaration_1;
        """,
    )

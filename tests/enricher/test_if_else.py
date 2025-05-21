import asyncio

from app.enricher import Constraints
from app.enricher.if_else import IfElseEnricherStrategy, get_pass_node_impl
from app.model.CompileRequest import (
    Edge,
    IfThenElseNode,
    ImplementationNode,
    NestedBlock,
)
from app.model.data_types import BitType, IntType, QubitType
from app.openqasm3.printer import leqo_dumps
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


def assert_if_else_enrichment(
    node: IfThenElseNode, constraints: Constraints, expected: str
) -> None:
    actual = next(iter(asyncio.run(IfElseEnricherStrategy().enrich(node, constraints))))
    print(actual.enriched_node.implementation)
    assert stem_qasm_string(expected) == stem_qasm_string(
        actual.enriched_node.implementation
    )


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


def test_basic() -> None:
    assert_if_else_enrichment(
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
        Constraints(
            requested_inputs={0: BitType(1), 1: QubitType(1)},
            optimizeWidth=False,
            optimizeDepth=False,
            frontend_name_to_index={"b": 0},
        ),
        """
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

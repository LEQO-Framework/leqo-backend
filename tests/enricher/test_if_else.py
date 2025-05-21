import asyncio

from app.enricher import Constraints
from app.enricher.if_else import IfElseEnricherStrategy, get_pass_node_impl
from app.model.CompileRequest import Edge, GateNode, IfThenElseNode, NestedBlock
from app.model.data_types import IntType, QubitType
from app.openqasm3.printer import leqo_dumps
from app.processing.utils import normalize_qasm_string


def assert_if_else_enrichment(
    node: IfThenElseNode, constraints: Constraints, expected: str
) -> None:
    actual = next(iter(asyncio.run(IfElseEnricherStrategy().enrich(node, constraints))))
    assert normalize_qasm_string(expected) == normalize_qasm_string(
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
    assert normalize_qasm_string(expected) == normalize_qasm_string(leqo_dumps(actual))


def test_basic() -> None:
    assert_if_else_enrichment(
        IfThenElseNode(
            id="if-node",
            condition="a == 3",
            thenBlock=NestedBlock(
                nodes=[GateNode(id="h-node", gate="h")],
                edges=[
                    Edge(source=("h-node", 0), target=("if-node", 0)),
                    Edge(source=("if-node", 0), target=("h-node", 0)),
                ],
            ),
            elseBlock=NestedBlock(
                nodes=[GateNode(id="x-node", gate="x")],
                edges=[
                    Edge(source=("x-node", 0), target=("if-node", 0)),
                    Edge(source=("if-node", 0), target=("x-node", 0)),
                ],
            ),
        ),
        Constraints(
            requested_inputs={0: QubitType(1)}, optimizeWidth=False, optimizeDepth=False
        ),
        "hi",
    )

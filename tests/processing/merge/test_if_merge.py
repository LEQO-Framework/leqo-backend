from uuid import UUID

from openqasm3.ast import BinaryExpression, BinaryOperator, BooleanLiteral, Identifier
from openqasm3.printer import dumps

from app.openqasm3.parser import leqo_parse
from app.processing.graph import (
    AncillaConnection,
    IOConnection,
    IOInfo,
    ProcessedProgramNode,
    ProgramGraph,
    ProgramNode,
    QubitInfo,
)
from app.processing.merge import merge_if_nodes
from app.processing.pre.io_parser import ParseAnnotationsVisitor
from app.processing.utils import normalize_qasm_string

manual_ios = tuple[tuple[int, int], tuple[int, int]]
manual_ancillas = tuple[tuple[int, list[int]], tuple[int, list[int]]]
manual_graph = tuple[list[str], list[manual_ios], list[manual_ancillas]]


def preprocess(node: ProgramNode, impl: str) -> ProcessedProgramNode:
    ast = leqo_parse(impl)

    io = IOInfo()
    qubit = QubitInfo()
    _ = ParseAnnotationsVisitor(io, qubit).visit(ast)

    return ProcessedProgramNode(node, ast, io, qubit)


def manual_to_graph(
    manual: manual_graph,
    if_node: ProcessedProgramNode,
    endif_node: ProcessedProgramNode,
) -> ProgramGraph:
    nodes, ios, ancillas = manual
    raws = [ProgramNode(str(i)) for i in range(len(nodes))]
    processed = [preprocess(raws[i], nodes[i]) for i in range(len(nodes))]
    raws = [if_node.raw, *raws, endif_node.raw]
    processed = [if_node, *processed, endif_node]
    result = ProgramGraph()
    result.append_node(if_node)
    result.append_node(endif_node)
    for p in processed:
        result.append_node(p)
    for s0, t0 in ios:
        result.append_edge(
            IOConnection((raws[s0[0]], s0[1]), (raws[t0[0]], t0[1])),
        )
    for s1, t1 in ancillas:
        result.append_edge(
            AncillaConnection(
                (raws[s1[0]], s1[1]),
                (raws[t1[0]], t1[1]),
            ),
        )
    return result


def assert_if_merge(  # noqa: PLR0913 Too many arguments in function definition (6 > 5)
    if_str: str,
    endif_str: str,
    then_manual: manual_graph,
    else_manual: manual_graph,
    condition_var: str,
    expected: str,
) -> None:
    if_node = preprocess(ProgramNode("if", id=UUID(int=888)), if_str)
    endif_node = preprocess(ProgramNode("endif", id=UUID(int=999)), endif_str)
    then_graph = manual_to_graph(then_manual, if_node, endif_node)
    else_graph = manual_to_graph(else_manual, if_node, endif_node)
    actual = dumps(
        merge_if_nodes(
            if_node,
            endif_node,
            then_graph,
            else_graph,
            BinaryExpression(
                BinaryOperator["=="],
                Identifier(condition_var),
                BooleanLiteral(True),
            ),
        ),
    )
    assert normalize_qasm_string(expected) == normalize_qasm_string(actual)


def test_basic_use_case() -> None:
    assert_if_merge(
        """
        OPENQASM 3.1;
        @leqo.input 0
        qubit[1] if_q;
        @leqo.output 0
        let if_o0 = if_q;
        @leqo.input 1
        bit if_b;
        @leqo.output 1
        let if_o1 = if_b;
        """,
        """
        OPENQASM 3.1;
        @leqo.input 0
        qubit[1] endif_q;
        @leqo.output 0
        let endif_o0 = endif_q;
        """,
        (
            [
                """
                OPENQASM 3.1;
                @leqo.input 0
                qubit[1] t0_q;
                h t0_q;
                @leqo.output 0
                let t0_o0 = t0_q;
                """,
            ],
            [
                ((0, 0), (1, 0)),
                ((1, 0), (2, 0)),
            ],
            [],
        ),
        (
            [
                """
                OPENQASM 3.1;
                @leqo.input 0
                qubit[1] e0_q;
                x e0_q;
                @leqo.output 0
                let e0_o0 = e0_q;
                """,
            ],
            [
                ((0, 0), (1, 0)),
                ((1, 0), (2, 0)),
            ],
            [],
        ),
        "b",
        """
        OPENQASM 3.1;
        @leqo.input 0
        qubit[1] if_q;
        let if_o0 = if_q;
        @leqo.input 1
        bit if_b;
        let if_o1 = if_b;
        let leqo_00000000000000000000000000000378_if_reg = if_q;
        if (b == true) {
            let t0_q = leqo_00000000000000000000000000000378_if_reg[{0}];
            h t0_q;
            let t0_o0 = t0_q;
        } else {
            let e0_q = leqo_00000000000000000000000000000378_if_reg[{0}];
            x e0_q;
            let e0_o0 = e0_q;
        }
        let endif_q = leqo_00000000000000000000000000000378_if_reg[{0}];
        @leqo.output 0
        let endif_o0 = endif_q;
        """,
    )


def test_complexer() -> None:
    assert_if_merge(
        """
        OPENQASM 3.1;
        @leqo.input 0
        qubit[4] if_q;
        @leqo.output 0
        let if_o0 = if_q;
        @leqo.input 1
        bit if_b;
        @leqo.output 1
        let if_o1 = if_b;
        """,
        """
        OPENQASM 3.1;
        @leqo.input 0
        qubit[2] endif_q0;
        @leqo.output 0
        let endif_o0 = endif_q0;
        @leqo.input 1
        qubit[2] endif_q1;
        @leqo.output 1
        let endif_o1 = endif_q1;
        """,
        (
            [
                """
                OPENQASM 3.1;
                @leqo.input 0
                qubit[4] t0_q;
                h t0_q;
                @leqo.output 0
                let t0_o0 = t0_q[0:1];
                @leqo.output 1
                let t0_o1 = t0_q[2:3];
                """,
                """
                OPENQASM 3.1;
                @leqo.input 0
                qubit[2] t1_q;
                h t1_q;
                @leqo.output 0
                let t1_o0 = t1_q;
                """,
            ],
            [
                ((0, 0), (1, 0)),
                ((1, 0), (2, 0)),
                ((2, 0), (3, 0)),
                ((1, 1), (3, 1)),
            ],
            [],
        ),
        (
            [
                """
                OPENQASM 3.1;
                @leqo.input 0
                qubit[4] e0_q0;
                qubit[4] e0_q1;
                @leqo.output 0
                let e0_o0 = e0_q0[0:1];
                @leqo.output 1
                let e0_o1 = e0_q0[2:3];
                """,
            ],
            [
                ((0, 0), (1, 0)),
                ((1, 0), (2, 0)),
                ((1, 1), (2, 1)),
            ],
            [],
        ),
        "b",
        """
        OPENQASM 3.1;
        @leqo.input 0
        qubit[4] if_q;
        let if_o0 = if_q;
        @leqo.input 1
        bit if_b;
        let if_o1 = if_b;
        qubit[4] leqo_00000000000000000000000000000378_ancillae;
        let leqo_00000000000000000000000000000378_if_reg = if_q ++ leqo_00000000000000000000000000000378_ancillae;
        if (b == true) {
            let t0_q = leqo_00000000000000000000000000000378_if_reg[{0, 1, 2, 3}];
            h t0_q;
            let t0_o0 = t0_q[0:1];
            let t0_o1 = t0_q[2:3];
            let t1_q = leqo_00000000000000000000000000000378_if_reg[{0, 1}];
            h t1_q;
            let t1_o0 = t1_q;
        } else {
            let e0_q0 = leqo_00000000000000000000000000000378_if_reg[{0, 1, 2, 3}];
            let e0_q1 = leqo_00000000000000000000000000000378_if_reg[{4, 5, 6, 7}];
            let e0_o0 = e0_q0[0:1];
            let e0_o1 = e0_q0[2:3];
        }
        let endif_q0 = leqo_00000000000000000000000000000378_if_reg[{0, 1}];
        @leqo.output 0
        let endif_o0 = endif_q0;
        let endif_q1 = leqo_00000000000000000000000000000378_if_reg[{2, 3}];
        @leqo.output 1
        let endif_o1 = endif_q1;
        """,
    )

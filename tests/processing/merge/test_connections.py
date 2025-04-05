from io import UnsupportedOperation
from uuid import uuid4

import pytest
from openqasm3.parser import parse
from openqasm3.printer import dumps

from app.processing.graph import (
    IOConnection,
    IOInfo,
    ProcessedProgramNode,
    ProgramGraph,
    ProgramNode,
    SectionInfo,
)
from app.processing.merge.connections import connect_qubits
from app.processing.pre.io_parser import ParseAnnotationsVisitor
from app.processing.utils import normalize_qasm_string


def str_to_nodes(code: str) -> tuple[ProgramNode, ProcessedProgramNode]:
    ast = parse(code)
    io = IOInfo()
    ParseAnnotationsVisitor(io).visit(ast)
    node = ProgramNode("xxx", code, None)
    return (
        node,
        ProcessedProgramNode(
            node,
            ast,
            SectionInfo(uuid4(), io),
            None,
        ),
    )


def assert_connections(
    inputs: list[str],
    expected: list[str],
    connections: list[tuple[tuple[int, int], tuple[int, int]]],
) -> None:
    graph = ProgramGraph()
    nodes = [str_to_nodes(code) for code in inputs]
    raw_nodes = []
    for node, processed in nodes:
        raw_nodes.append(node)
        graph.append_node(processed)
    graph.append_edges(
        *[
            IOConnection(
                (raw_nodes[con[0][0]], con[0][1]),
                (raw_nodes[con[1][0]], con[1][1]),
            )
            for con in connections
        ],
    )
    connect_qubits(graph)
    actual = [
        normalize_qasm_string(dumps(graph.get_data_node(node).implementation))
        for node in graph.nodes()
    ]
    expected = [normalize_qasm_string(code) for code in expected]
    assert actual == expected


def test_no_connections() -> None:
    inputs = [
        """
        qubit[3] c0_q0;
        """,
        """
        qubit[3] c1_q0;
        """,
    ]
    connections: list[tuple[tuple[int, int], tuple[int, int]]] = []
    expected = [
        """
        let c0_q0 = leqo_reg[{0, 1, 2}];
        """,
        """
        let c1_q0 = leqo_reg[{3, 4, 5}];
        """,
    ]
    assert_connections(inputs, expected, connections)


def test_single_connections() -> None:
    inputs = [
        """
        qubit[3] c0_q0;
        @leqo.output 0
        let _out = c0_q0;
        """,
        """
        @leqo.input 0
        qubit[3] c1_q0;
        """,
    ]
    connections = [((0, 0), (1, 0))]
    expected = [
        """
        let c0_q0 = leqo_reg[{0, 1, 2}];
        @leqo.output 0
        let _out = c0_q0;
        """,
        """
        @leqo.input 0
        let c1_q0 = leqo_reg[{0, 1, 2}];
        """,
    ]
    assert_connections(inputs, expected, connections)


def test_all() -> None:
    inputs = [
        """
        qubit[4] c0_q0;
        @leqo.output 0
        let _out_c0_0 = c0_q0[0:1];
        @leqo.output 1
        let _out_c0_1 = c0_q0[2:3];
        """,
        """
        @leqo.input 0
        qubit[2] c1_q0;
        @leqo.output 0
        let _out_c1_0 = c1_q0[0];
        """,
        """
        @leqo.input 0
        qubit[2] c2_q0;
        @leqo.input 1
        qubit c2_q1;
        """,
    ]
    connections = [
        ((0, 0), (1, 0)),
        ((0, 1), (2, 0)),
        ((1, 0), (2, 1)),
    ]
    expected = [
        """
        let c0_q0 = leqo_reg[{0, 1, 2, 3}];
        @leqo.output 0
        let _out_c0_0 = c0_q0[0:1];
        @leqo.output 1
        let _out_c0_1 = c0_q0[2:3];
        """,
        """
        @leqo.input 0
        let c1_q0 = leqo_reg[{0, 1}];
        @leqo.output 0
        let _out_c1_0 = c1_q0[0];
        """,
        """
        @leqo.input 0
        let c2_q0 = leqo_reg[{2, 3}];
        @leqo.input 1
        let c2_q1 = leqo_reg[{0}];
        """,
    ]
    assert_connections(inputs, expected, connections)


def test_raise_on_mismatched_connection_size() -> None:
    inputs = [
        """
        qubit[1] c0_q0;
        @leqo.output 0
        let _out = c0_q0;
        """,
        """
        @leqo.input 0
        qubit[100] c1_q0;
        """,
    ]
    connections: list[tuple[tuple[int, int], tuple[int, int]]] = [
        ((0, 0), (1, 0)),
    ]
    with pytest.raises(UnsupportedOperation):
        assert_connections(inputs, [], connections)

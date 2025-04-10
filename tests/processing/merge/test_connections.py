from io import UnsupportedOperation
from uuid import uuid4

import pytest
from openqasm3.parser import parse
from openqasm3.printer import dumps

from app.processing.graph import (
    AncillaConnection,
    IOConnection,
    ProcessedProgramNode,
    ProgramGraph,
    ProgramNode,
    SectionInfo,
)
from app.processing.io_info import CombinedIOInfo
from app.processing.merge.connections import connect_qubits
from app.processing.pre.io_parser import ParseAnnotationsVisitor
from app.processing.utils import normalize_qasm_string


def str_to_nodes(index: int, code: str) -> tuple[ProgramNode, ProcessedProgramNode]:
    ast = parse(code)
    io = CombinedIOInfo()
    ParseAnnotationsVisitor(io).visit(ast)
    node = ProgramNode(str(index), code, None)
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
    io_connections: list[tuple[tuple[int, int], tuple[int, int]]] | None = None,
    ancilla_connections: list[tuple[tuple[int, list[int]], tuple[int, list[int]]]]
    | None = None,
) -> None:
    graph = ProgramGraph()
    nodes = [str_to_nodes(i, code) for i, code in enumerate(inputs)]
    raw_nodes = []
    for node, processed in nodes:
        raw_nodes.append(node)
        graph.append_node(processed)
    if io_connections is not None:
        graph.append_edges(
            *[
                IOConnection(
                    (raw_nodes[con[0][0]], con[0][1]),
                    (raw_nodes[con[1][0]], con[1][1]),
                )
                for con in io_connections
            ],
        )
    if ancilla_connections is not None:
        graph.append_edges(
            *[
                AncillaConnection(
                    (raw_nodes[con[0][0]], con[0][1]),
                    (raw_nodes[con[1][0]], con[1][1]),
                )
                for con in ancilla_connections
            ],
        )
    connect_qubits(graph, "leqo_reg")
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


def test_single_ancilla_connection() -> None:
    inputs = [
        """
        qubit[3] c0_q0;
        """,
        """
        qubit[3] c1_q0;
        """,
    ]
    connections = [((0, [0, 1]), (1, [0, 1]))]
    expected = [
        """
        let c0_q0 = leqo_reg[{0, 1, 2}];
        """,
        """
        let c1_q0 = leqo_reg[{0, 1, 3}];
        """,
    ]
    assert_connections(inputs, expected, ancilla_connections=connections)


def test_io_ancilla_connection_mix() -> None:
    inputs = [
        """
        qubit[3] c0_q0;
        qubit[2] c0_q1;
        @leqo.output 0
        let _out = c0_q0;
        """,
        """
        @leqo.input 0
        qubit[3] c1_q0;
        qubit[3] c1_q1;
        """,
    ]
    io_connections = [((0, 0), (1, 0))]
    ancilla_connections = [
        ((0, [3, 4]), (1, [3, 4])),
    ]
    expected = [
        """
        let c0_q0 = leqo_reg[{0, 1, 2}];
        let c0_q1 = leqo_reg[{3, 4}];
        @leqo.output 0
        let _out = c0_q0;
        """,
        """
        @leqo.input 0
        let c1_q0 = leqo_reg[{0, 1, 2}];
        let c1_q1 = leqo_reg[{3, 4, 5}];
        """,
    ]
    assert_connections(inputs, expected, io_connections, ancilla_connections)


def test_one_output_to_two_inputs() -> None:
    inputs = [
        """
        qubit[2] c0_q0;
        @leqo.output 0
        let _out = c0_q0;
        """,
        """
        @leqo.input 0
        qubit[2] c1_q0;
        """,
        """
        @leqo.input 0
        qubit[2] c2_q0;
        """,
    ]
    connections = [
        ((0, 0), (1, 0)),
        ((0, 0), (2, 0)),
    ]
    expected = [
        """
        let c0_q0 = leqo_reg[{0, 1}];
        @leqo.output 0
        let _out = c0_q0;
        """,
        """
        @leqo.input 0
        let c1_q0 = leqo_reg[{0, 1}];
        """,
        """
        @leqo.input 0
        let c2_q0 = leqo_reg[{0, 1}];
        """,
    ]
    assert_connections(inputs, expected, connections)


def test_two_inputs_to_one_output() -> None:
    inputs = [
        """
        qubit[2] c0_q0;
        @leqo.output 0
        let _out_c0_0 = c0_q0;
        """,
        """
        qubit[2] c1_q0;
        @leqo.output 0
        let _out_c1_0 = c1_q0;
        """,
        """
        @leqo.input 0
        qubit[2] c2_q0;
        """,
    ]
    connections = [
        ((0, 0), (2, 0)),
        ((1, 0), (2, 0)),
    ]
    expected = [
        """
        let c0_q0 = leqo_reg[{0, 1}];
        @leqo.output 0
        let _out_c0_0 = c0_q0;
        """,
        """
        let c1_q0 = leqo_reg[{0, 1}];
        @leqo.output 0
        let _out_c1_0 = c1_q0;
        """,
        """
        @leqo.input 0
        let c2_q0 = leqo_reg[{0, 1}];
        """,
    ]
    assert_connections(inputs, expected, connections)


def test_connection_chain() -> None:
    inputs = [
        """
        qubit[5] c0_q0;
        @leqo.output 0
        let _out_c0_0 = c0_q0[0:-2];
        """,
        """
        @leqo.input 0
        qubit[4] c1_q0;
        @leqo.output 0
        let _out_c1_0 = c1_q0[0:-2];
        """,
        """
        @leqo.input 0
        qubit[3] c2_q0;
        """,
    ]
    connections = [
        ((0, 0), (1, 0)),
        ((1, 0), (2, 0)),
    ]
    expected = [
        """
        let c0_q0 = leqo_reg[{0, 1, 2, 3, 4}];
        @leqo.output 0
        let _out_c0_0 = c0_q0[0:-2];
        """,
        """
        @leqo.input 0
        let c1_q0 = leqo_reg[{0, 1, 2, 3}];
        @leqo.output 0
        let _out_c1_0 = c1_q0[0:-2];
        """,
        """
        @leqo.input 0
        let c2_q0 = leqo_reg[{0, 1, 2}];
        """,
    ]
    assert_connections(inputs, expected, connections)


def test_complex() -> None:
    inputs = [
        """
        qubit[6] c0_q0;
        @leqo.output 0
        let _out_c0_0 = c0_q0[0:1];
        @leqo.output 1
        let _out_c0_1 = c0_q0[2:3];
        """,
        """
        @leqo.input 0
        qubit[2] c1_q0;
        qubit c1_q1;
        @leqo.output 0
        let _out_c1_0 = c1_q0[0] ++ c1_q1;
        """,
        """
        @leqo.input 0
        qubit[2] c2_q0;
        @leqo.input 1
        qubit[2] c2_q1;
        qubit c2_q2;
        """,
    ]
    io_connections = [
        ((0, 0), (1, 0)),
        ((0, 1), (2, 0)),
        ((1, 0), (2, 1)),
    ]
    ancilla_connections = [
        ((0, [4]), (1, [2])),
        ((0, [5]), (2, [4])),
    ]
    expected = [
        """
        let c0_q0 = leqo_reg[{0, 1, 2, 3, 4, 5}];
        @leqo.output 0
        let _out_c0_0 = c0_q0[0:1];
        @leqo.output 1
        let _out_c0_1 = c0_q0[2:3];
        """,
        """
        @leqo.input 0
        let c1_q0 = leqo_reg[{0, 1}];
        let c1_q1 = leqo_reg[{4}];
        @leqo.output 0
        let _out_c1_0 = c1_q0[0] ++ c1_q1;
        """,
        """
        @leqo.input 0
        let c2_q0 = leqo_reg[{2, 3}];
        @leqo.input 1
        let c2_q1 = leqo_reg[{0, 4}];
        let c2_q2 = leqo_reg[{5}];
        """,
    ]
    assert_connections(inputs, expected, io_connections, ancilla_connections)


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
    with pytest.raises(
        UnsupportedOperation,
        match="Mismatched size in model connection between 0 and 1",
    ):
        assert_connections(inputs, [], connections)


def test_raise_on_missing_input_index() -> None:
    inputs = [
        """
        qubit[3] c0_q0;
        @leqo.output 0
        let _out = c0_q0;
        """,
        """
        qubit[3] c1_q0;
        """,
    ]
    connections: list[tuple[tuple[int, int], tuple[int, int]]] = [
        ((0, 0), (0, 0)),
    ]
    with pytest.raises(
        UnsupportedOperation,
        match="Unsupported: Input with index 0 into 0 modeled, but no such annotation.",
    ):
        assert_connections(inputs, [], connections)


def test_raise_on_missing_output_index() -> None:
    inputs = [
        """
        qubit[3] c0_q0;
        let _out = c0_q0;
        """,
        """
        @leqo.input 0
        qubit[3] c1_q0;
        """,
    ]
    connections: list[tuple[tuple[int, int], tuple[int, int]]] = [
        ((0, 0), (0, 0)),
    ]
    with pytest.raises(
        UnsupportedOperation,
        match="Unsupported: Output with index 0 from 0 modeled, but no such annotation.",
    ):
        assert_connections(inputs, [], connections)

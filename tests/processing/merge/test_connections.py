import re

import pytest
from openqasm3.parser import parse
from openqasm3.printer import dumps

from app.transformation_manager.graph import (
    AncillaConnection,
    IOConnection,
    IOInfo,
    ProcessedProgramNode,
    ProgramGraph,
    ProgramNode,
    QubitInfo,
)
from app.transformation_manager.merge.connections import connect_qubits
from app.transformation_manager.merge.utils import MergeException
from app.transformation_manager.pre.io_parser import ParseAnnotationsVisitor
from app.transformation_manager.utils import normalize_qasm_string


def str_to_nodes(index: int, code: str) -> ProcessedProgramNode:
    node = ProgramNode(str(index), code)

    implementation = parse(code)

    io = IOInfo()
    qubit = QubitInfo()
    _ = ParseAnnotationsVisitor(io, qubit).visit(implementation)

    return ProcessedProgramNode(node, implementation, io, qubit)


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
    for processed in nodes:
        raw_nodes.append(processed.raw)
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


def test_keep_qubit_type() -> None:
    inputs = [
        """
        qubit[3] q0;
        qubit[1] q1;
        qubit q2;
        """,
    ]
    connections: list[tuple[tuple[int, int], tuple[int, int]]] = []
    expected = [
        """
        let q0 = leqo_reg[{0, 1, 2}];
        let q1 = leqo_reg[{3}];
        let q2 = leqo_reg[4];
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


def test_classical_simple() -> None:
    inputs = [
        """
        int c0_i0;
        @leqo.output 0
        let _out = c0_i0;
        """,
        """
        @leqo.input 0
        int c1_i0;
        """,
    ]
    io_connections = [((0, 0), (1, 0))]
    expected = [
        """
        int c0_i0;
        @leqo.output 0
        let _out = c0_i0;
        """,
        """
        @leqo.input 0
        let c1_i0 = _out;
        """,
    ]
    assert_connections(inputs, expected, io_connections)


def test_classical_one_output_to_two_inputs() -> None:
    inputs = [
        """
        bit[16] c0_c0;
        @leqo.output 0
        let _out0 = c0_c0[0:3];
        @leqo.output 1
        let _out1 = c0_c0[4:7];
        """,
        """
        @leqo.input 0
        bit[4] c1_c0;
        """,
        """
        @leqo.input 0
        bit[4] c2_c0;
        """,
    ]
    io_connections = [
        ((0, 0), (1, 0)),
        ((0, 1), (2, 0)),
    ]
    expected = [
        """
        bit[16] c0_c0;
        @leqo.output 0
        let _out0 = c0_c0[0:3];
        @leqo.output 1
        let _out1 = c0_c0[4:7];
        """,
        """
        @leqo.input 0
        let c1_c0 = _out0;
        """,
        """
        @leqo.input 0
        let c2_c0 = _out1;
        """,
    ]
    assert_connections(inputs, expected, io_connections)


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
        int c0_i0;
        @leqo.output 0
        let _out_c0_0 = c0_q0[0:1];
        @leqo.output 1
        let _out_c0_1 = c0_q0[2:3];
        @leqo.output 2
        let _out_c0_2 = c0_i0;
        """,
        """
        @leqo.input 0
        qubit[2] c1_q0;
        qubit[1] c1_q1;
        @leqo.output 0
        let _out_c1_0 = c1_q0[{0}] ++ c1_q1;
        """,
        """
        @leqo.input 0
        qubit[2] c2_q0;
        @leqo.input 1
        qubit[2] c2_q1;
        @leqo.input 2
        int c2_i0;
        qubit[1] c2_q2;
        """,
    ]
    io_connections = [
        ((0, 0), (1, 0)),
        ((0, 1), (2, 0)),
        ((0, 2), (2, 2)),
        ((1, 0), (2, 1)),
    ]
    ancilla_connections = [
        ((0, [4]), (1, [2])),
        ((0, [5]), (2, [4])),
    ]
    expected = [
        """
        let c0_q0 = leqo_reg[{0, 1, 2, 3, 4, 5}];
        int c0_i0;
        @leqo.output 0
        let _out_c0_0 = c0_q0[0:1];
        @leqo.output 1
        let _out_c0_1 = c0_q0[2:3];
        @leqo.output 2
        let _out_c0_2 = c0_i0;
        """,
        """
        @leqo.input 0
        let c1_q0 = leqo_reg[{0, 1}];
        let c1_q1 = leqo_reg[{4}];
        @leqo.output 0
        let _out_c1_0 = c1_q0[{0}] ++ c1_q1;
        """,
        """
        @leqo.input 0
        let c2_q0 = leqo_reg[{2, 3}];
        @leqo.input 1
        let c2_q1 = leqo_reg[{0, 4}];
        @leqo.input 2
        let c2_i0 = _out_c0_2;
        let c2_q2 = leqo_reg[{5}];
        """,
    ]
    assert_connections(inputs, expected, io_connections, ancilla_connections)


def test_raise_on_mismatched_qubit_size() -> None:
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
        MergeException,
        match=re.escape(
            "Unsupported: Mismatched types in IOConnection QubitType(size=1) != QubitType(size=100)"
        ),
    ):
        assert_connections(inputs, [], connections)


def test_raise_on_classical_to_qubit() -> None:
    inputs = [
        """
        qubit[8] c0_q0;
        @leqo.output 0
        let _out = c0_q0;
        """,
        """
        @leqo.input 0
        bit[8] c1_c0;
        """,
    ]
    connections: list[tuple[tuple[int, int], tuple[int, int]]] = [
        ((0, 0), (1, 0)),
    ]
    with pytest.raises(
        MergeException,
        match=r"""^Unsupported: Try to connect qubit with classical

Index 0 from 1 tries to
connect to index 0 from 1$""",
    ):
        assert_connections(inputs, [], connections)


def test_raise_on_mismatched_classic_type() -> None:
    inputs = [
        """
        int c0_i0;
        @leqo.output 0
        let _out = c0_i0;
        """,
        """
        @leqo.input 0
        bool c1_b0;
        """,
    ]
    connections: list[tuple[tuple[int, int], tuple[int, int]]] = [
        ((0, 0), (1, 0)),
    ]
    with pytest.raises(
        MergeException,
        match=r"""^Unsupported: Mismatched types in IOConnection

output _out has type IntType\(size=32\)
input c1_b0 has type BoolType\(\)$""",
    ):
        assert_connections(inputs, [], connections)


def test_raise_on_mismatched_classic_size() -> None:
    inputs = [
        """
        int[16] c0_i0;
        @leqo.output 0
        let _out = c0_i0;
        """,
        """
        @leqo.input 0
        int[32] c1_i0;
        """,
    ]
    connections: list[tuple[tuple[int, int], tuple[int, int]]] = [
        ((0, 0), (1, 0)),
    ]
    with pytest.raises(
        MergeException,
        match=r"""^Unsupported: Mismatched types in IOConnection

output _out has type IntType\(size=16\)
input c1_i0 has type IntType\(size=32\)$""",
    ):
        assert_connections(inputs, [], connections)


def test_raise_two_classical_outputs_into_one_input() -> None:
    inputs = [
        """
        int[16] c0_i0;
        @leqo.output 0
        let _out0 = c0_i0;
        """,
        """
        int[16] c1_i0;
        @leqo.output 0
        let _out1 = c1_i0;
        """,
        """
        @leqo.input 0
        int[16] c2_i0;
        """,
    ]
    connections: list[tuple[tuple[int, int], tuple[int, int]]] = [
        ((0, 0), (2, 0)),
        ((1, 0), (2, 0)),
    ]
    with pytest.raises(
        MergeException,
        match=r"""^Unsupported: Multiple inputs into classical

Both _out0 and _out1
are input to c2_i0 but only one is allowed.$""",
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
        MergeException,
        match=r"""^Unsupported: Missing input index in connection

Index 0 from 0 modeled,
but no such annotation was found.$""",
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
        MergeException,
        match=r"""^Unsupported: Missing output index in connection

Index 0 from 0 modeled,
but no such annotation was found.$""",
    ):
        assert_connections(inputs, [], connections)

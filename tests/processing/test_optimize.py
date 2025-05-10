from openqasm3.parser import parse
from openqasm3.printer import dumps

from app.processing.graph import (
    IOConnection,
    IOInfo,
    ProcessedProgramNode,
    ProgramGraph,
    ProgramNode,
    QubitInfo,
)
from app.processing.merge import merge_nodes
from app.processing.optimize import optimize
from app.processing.pre.io_parser import ParseAnnotationsVisitor
from app.processing.utils import normalize_qasm_string

IOConIndexed = tuple[tuple[int, int], tuple[int, int]]
AncillaConIndexed = tuple[tuple[int, list[int]], tuple[int, list[int]]]


def str_to_nodes(index: int, code: str, is_ancilla_node: bool) -> ProcessedProgramNode:
    node = ProgramNode(str(index), code, is_ancilla_node)

    implementation = parse(code)

    io = IOInfo()
    qubit = QubitInfo()
    _ = ParseAnnotationsVisitor(io, qubit).visit(implementation)

    return ProcessedProgramNode(node, implementation, io, qubit)


def assert_optimize(
    before: list[str],
    expected: str,
    io_connections: list[IOConIndexed] | None = None,
    ancilla_nodes: dict[int, bool] | None = None,
) -> None:
    ancilla_nodes = (
        dict.fromkeys(range(len(before)), False)
        if ancilla_nodes is None
        else ancilla_nodes
    )
    graph = ProgramGraph()
    nodes = [str_to_nodes(i, code, ancilla_nodes[i]) for i, code in enumerate(before)]
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
    optimize(graph)
    actual = normalize_qasm_string(dumps(merge_nodes(graph)))
    expected = normalize_qasm_string(expected)
    assert actual == expected


def test_obvious_ancialla_connection() -> None:
    before = [
        """
        qubit[5] c0_q0;
        @leqo.reusable
        let _reuse = c0_q0;
        """,
        """
        qubit[5]  c1_q0;
        """,
    ]
    expected = """
    OPENQASM 3.1;
    qubit[5] leqo_reg;
    let c0_q0 = leqo_reg[{0, 1, 2, 3, 4}];
    @leqo.reusable
    let _reuse = c0_q0;
    let c1_q0 = leqo_reg[{0, 1, 2, 3, 4}];
    """
    assert_optimize(before, expected)


def test_respect_new_ancillas_via_ancilla_node() -> None:
    before = [
        """
        qubit[5] c0_q0;
        @leqo.reusable
        let _reuse = c0_q0;
        """,
        """
        qubit[5]  c1_q0;
        """,
    ]
    expected = """
    OPENQASM 3.1;
    qubit[10] leqo_reg;
    let c0_q0 = leqo_reg[{0, 1, 2, 3, 4}];
    @leqo.reusable
    let _reuse = c0_q0;
    let c1_q0 = leqo_reg[{5, 6, 7, 8, 9}];
    """
    ancilla_nodes = {0: False, 1: True}
    assert_optimize(before, expected, ancilla_nodes=ancilla_nodes)


def test_obvious_uncompute() -> None:
    before = [
        """
        qubit[5] c0_q0;
        @leqo.uncompute
        if (false) {
            @leqo.reusable
            let _reuse = c0_q0;
        }
        """,
        """
        qubit[5]  c1_q0;
        """,
    ]
    expected = """
    OPENQASM 3.1;
    qubit[5] leqo_reg;
    let c0_q0 = leqo_reg[{0, 1, 2, 3, 4}];
    @leqo.reusable
    let _reuse = c0_q0;
    let c1_q0 = leqo_reg[{0, 1, 2, 3, 4}];
    """
    assert_optimize(before, expected)


def test_removed_uncompute() -> None:
    before = [
        """
        qubit[5] c0_q0;
        @leqo.output 0
        let _out = c0_q0[0];
        @leqo.uncompute
        if (false) {
            @leqo.reusable
            let _reuse = c0_q0[1:];
        }
        """,
        """
        @leqo.input 0
        qubit[1] c1_q0;
        """,
    ]
    io_connections = [((0, 0), (1, 0))]
    expected = """
    OPENQASM 3.1;
    qubit[5] leqo_reg;
    let c0_q0 = leqo_reg[{0, 1, 2, 3, 4}];
    @leqo.output 0
    let _out = c0_q0[0];
    @leqo.input 0
    let c1_q0 = leqo_reg[{0}];
    """
    assert_optimize(before, expected, io_connections)


def test_keep_io_connections() -> None:
    before = [
        """
        qubit[5]  c0_q0;
        @leqo.output 0
        let _out = c0_q0;
        """,
        """
        @leqo.input 0
        qubit[5] c1_q0;
        qubit[5] c1_q1;
        @leqo.reusable
        let _reuse = c1_q1;
        """,
    ]
    io_connections = [((0, 0), (1, 0))]
    expected = """
    OPENQASM 3.1;
    qubit[10] leqo_reg;
    let c0_q0 = leqo_reg[{0, 1, 2, 3, 4}];
    @leqo.output 0
    let _out = c0_q0;
    @leqo.input 0
    let c1_q0 = leqo_reg[{0, 1, 2, 3, 4}];
    let c1_q1 = leqo_reg[{5, 6, 7, 8, 9}];
    @leqo.reusable
    let _reuse = c1_q1;
    """
    assert_optimize(before, expected, io_connections)


def test_simple_find_best_sort() -> None:
    before = [
        """
        qubit[1] c0_q0;
        qubit[5] c0_q1;
        @leqo.output 0
        let c0_out0 = c0_q0;
        @leqo.output 1
        let c0_out1 = c0_q1;
        """,
        """
        @leqo.input 0
        qubit[1]  c1_q0;
        @leqo.output 0
        let c1_out0 = c1_q0;

        qubit[4] c1_q1;
        """,
        """
        @leqo.input 0
        qubit[5]  c2_q0;
        @leqo.output 0
        let c2_out0 = c2_q0[0];

        @leqo.reusable
        let _reuse = c2_q0[1:4];
        """,
        """
        @leqo.input 0
        qubit[1]  c3_q0;
        @leqo.input 1
        qubit[1]  c3_q1;
        """,
    ]
    io_connections = [
        ((0, 0), (1, 0)),
        ((0, 1), (2, 0)),
        ((1, 0), (3, 0)),
        ((2, 0), (3, 1)),
    ]
    expected = """
    OPENQASM 3.1;
    qubit[6] leqo_reg;
    let c0_q0 = leqo_reg[{0}];
    let c0_q1 = leqo_reg[{1, 2, 3, 4, 5}];
    @leqo.output 0
    let c0_out0 = c0_q0;
    @leqo.output 1
    let c0_out1 = c0_q1;
    @leqo.input 0
    let c2_q0 = leqo_reg[{1, 2, 3, 4, 5}];
    @leqo.output 0
    let c2_out0 = c2_q0[0];
    @leqo.reusable
    let _reuse = c2_q0[1:4];
    @leqo.input 0
    let c1_q0 = leqo_reg[{0}];
    @leqo.output 0
    let c1_out0 = c1_q0;
    let c1_q1 = leqo_reg[{2, 3, 4, 5}];
    @leqo.input 0
    let c3_q0 = leqo_reg[{0}];
    @leqo.input 1
    let c3_q1 = leqo_reg[{1}];
    """
    assert_optimize(before, expected, io_connections)


def test_simple_avoid_uncompute() -> None:
    before = [
        """
        qubit[1] c0_q0;
        qubit[1] c0_q1;
        @leqo.output 0
        let c0_out0 = c0_q0;
        @leqo.output 1
        let c0_out1 = c0_q1;
        """,
        """
        @leqo.input 0
        qubit[1] c1_q0;
        @leqo.output 0
        let c1_out0 = c1_q0;

        qubit[5] c1_q1;
        @leqo.uncompute
        if (false) {
            @leqo.reusable
            let c1_reuse0 = c1_q1;
        }
        """,
        """
        @leqo.input 0
        qubit[1] c2_q0;
        @leqo.output 0
        let c2_out0 = c2_q0;

        qubit[5] c2_q1;
        @leqo.reusable
        let c2_reuse0 = c2_q1;
        """,
        """
        @leqo.input 0
        qubit[1] c3_q0;
        @leqo.input 1
        qubit[1] c3_q1;
        """,
    ]
    io_connections = [
        ((0, 0), (1, 0)),
        ((0, 1), (2, 0)),
        ((1, 0), (3, 0)),
        ((2, 0), (3, 1)),
    ]
    expected = """
    OPENQASM 3.1;
    qubit[7] leqo_reg;
    let c0_q0 = leqo_reg[{0}];
    let c0_q1 = leqo_reg[{1}];
    @leqo.output 0
    let c0_out0 = c0_q0;
    @leqo.output 1
    let c0_out1 = c0_q1;
    @leqo.input 0
    let c2_q0 = leqo_reg[{1}];
    @leqo.output 0
    let c2_out0 = c2_q0;
    let c2_q1 = leqo_reg[{2, 3, 4, 5, 6}];
    @leqo.reusable
    let c2_reuse0 = c2_q1;
    @leqo.input 0
    let c1_q0 = leqo_reg[{0}];
    @leqo.output 0
    let c1_out0 = c1_q0;
    let c1_q1 = leqo_reg[{2, 3, 4, 5, 6}];
    @leqo.input 0
    let c3_q0 = leqo_reg[{0}];
    @leqo.input 1
    let c3_q1 = leqo_reg[{1}];
    """
    assert_optimize(before, expected, io_connections)

from app.openqasm3.printer import leqo_dumps
from app.processing.graph import (
    IOConnection,
    ProgramGraph,
    ProgramNode,
)
from app.processing.merge import merge_nodes
from app.processing.pre import preprocess
from app.processing.utils import normalize_qasm_string


def assert_merge(
    codes: list[str],
    connections: list[tuple[tuple[int, int], tuple[int, int]]],
    expected: str,
) -> None:
    nodes = []
    for i, code in enumerate(codes):
        nodes.append(preprocess(ProgramNode(str(i)), code))

    graph = ProgramGraph()
    graph.append_nodes(*nodes)
    for conn in connections:
        graph.append_edge(
            IOConnection(
                (nodes[conn[0][0]].raw, conn[0][1]),
                (nodes[conn[1][0]].raw, conn[1][1]),
            ),
        )

    actual = normalize_qasm_string(leqo_dumps(merge_nodes(graph)))

    for i, node in enumerate(nodes):
        expected = expected.replace(f"leqo_node{i}", f"leqo_{node.id.hex}")
    expected = normalize_qasm_string(expected)

    assert actual == expected


def test_pseudo_merge_single() -> None:
    codes = [
        """
        OPENQASM 3.1;
        qubit[1] a;
        """,
    ]
    connections: list[tuple[tuple[int, int], tuple[int, int]]] = []
    expected = """
    OPENQASM 3.1;
    qubit[1] leqo_reg;
    /* Start node 0 */
    let leqo_node0_a = leqo_reg[{0}];
    /* End node 0 */
    """
    assert_merge(codes, connections, expected)


def test_merge_two_nodes() -> None:
    codes = [
        """
        OPENQASM 3.1;
        qubit[1] a;
        @leqo.output 0
        let _out = a;
        """,
        """
        OPENQASM 3.1;
        @leqo.input 0
        qubit[1] a;
        """,
    ]
    connections = [((0, 0), (1, 0))]
    expected = """
    OPENQASM 3.1;
    qubit[1] leqo_reg;
    /* Start node 0 */
    let leqo_node0_a = leqo_reg[{0}];
    @leqo.output 0
    let leqo_node0__out = leqo_node0_a;
    /* End node 0 */
    /* Start node 1 */
    @leqo.input 0
    let leqo_node1_a = leqo_reg[{0}];
    /* End node 1 */
    """
    assert_merge(codes, connections, expected)


def test_complex_merge() -> None:
    codes = [
        """
        OPENQASM 3.1;
        qubit[4] q;
        @leqo.output 0
        let _out0 = q[0:2];
        @leqo.output 1
        let _out1 = q[{3}];
        """,
        """
        OPENQASM 3.1;
        @leqo.input 0
        qubit[1] q;
        @leqo.output 0
        let _out0 = q;
        """,
        """
        OPENQASM 3.1;
        @leqo.input 0
        qubit[1] q0;
        @leqo.input 1
        qubit[3] q1;
        """,
    ]
    connections = [
        ((0, 0), (2, 1)),
        ((0, 1), (1, 0)),
        ((1, 0), (2, 0)),
    ]
    expected = """
    OPENQASM 3.1;
    qubit[4] leqo_reg;
    /* Start node 0 */
    let leqo_node0_q = leqo_reg[{0, 1, 2, 3}];
    @leqo.output 0
    let leqo_node0__out0 = leqo_node0_q[0:2];
    @leqo.output 1
    let leqo_node0__out1 = leqo_node0_q[{3}];
    /* End node 0 */
    /* Start node 1 */
    @leqo.input 0
    let leqo_node1_q = leqo_reg[{3}];
    @leqo.output 0
    let leqo_node1__out0 = leqo_node1_q;
    /* End node 1 */
    /* Start node 2 */
    @leqo.input 0
    let leqo_node2_q0 = leqo_reg[{3}];
    @leqo.input 1
    let leqo_node2_q1 = leqo_reg[{0, 1, 2}];
    /* End node 2 */
    """
    assert_merge(codes, connections, expected)

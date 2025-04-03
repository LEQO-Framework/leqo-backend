from textwrap import dedent

from app.processing import merge_nodes, preprocess, print_program
from app.processing.graph import (
    IOConnection,
    ProgramGraph,
    ProgramNode,
)


def test_merge_nodes() -> None:
    node0 = preprocess(ProgramNode("0", "qubit last;"))
    node1 = preprocess(ProgramNode("1", "qubit a;"))
    node2 = preprocess(ProgramNode("2", "qubit b;"))

    graph = ProgramGraph()
    graph.append_nodes(node0, node1, node2)
    graph.append_edges(
        IOConnection((node1.raw, 0), (node0.raw, 0)),
        IOConnection((node2.raw, 0), (node0.raw, 0)),
        IOConnection((node1.raw, 0), (node2.raw, 0)),
    )

    program = merge_nodes(graph)
    result = print_program(program)
    assert result == dedent(f"""\
        OPENQASM 3.1;
        /* Start node 1 */;
        qubit leqo_{node1.info.id.hex}_declaration0;
        /* End node 1 */;
        /* Start node 2 */;
        qubit leqo_{node2.info.id.hex}_declaration0;
        /* End node 2 */;
        /* Start node 0 */;
        qubit leqo_{node0.info.id.hex}_declaration0;
        /* End node 0 */;
        """)

from textwrap import dedent

from app.processing import merge_nodes, print_program
from app.processing.graph import (
    IOConnection,
    ProgramGraph,
    ProgramNode,
    QasmImplementation,
)


def test_merge_nodes() -> None:
    node0 = ProgramNode("0", QasmImplementation.create("qubit last;"))
    node1 = ProgramNode("42", QasmImplementation.create("qubit a;"))
    node2 = ProgramNode("420", QasmImplementation.create("qubit b;"))

    graph = ProgramGraph()
    graph.append_nodes((node0, node1, node2))
    graph.append_edges(
        (
            IOConnection((node1, 0), (node0, 0), 0),
            IOConnection((node2, 0), (node0, 0), 0),
            IOConnection((node1, 0), (node2, 0), 0),
        ),
    )

    program = merge_nodes(graph)
    result = print_program(program)
    assert result == dedent("""\
        OPENQASM 3.1;
        /* Start node 42 */;
        qubit leqo_section0_declaration0;
        /* End node 42 */;
        /* Start node 420 */;
        qubit leqo_section1_declaration0;
        /* End node 420 */;
        /* Start node 0 */;
        qubit leqo_section2_declaration0;
        /* End node 0 */;
        """)

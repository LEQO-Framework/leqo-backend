from openqasm3.ast import Identifier, IntegerLiteral, Program, QubitDeclaration

from app.openqasm3.ast import CommentStatement
from app.transformation_manager.post import postprocess
from app.transformation_manager.post.qiskit_compat import apply_qiskit_compatibility


def _sample_program() -> Program:
    return Program(
        [
            CommentStatement("Start node literal_a"),
            QubitDeclaration(Identifier("lit_qubit"), IntegerLiteral(1)),
            CommentStatement("End node literal_a"),
            CommentStatement("Start node useful"),
            QubitDeclaration(Identifier("work"), IntegerLiteral(1)),
            CommentStatement("End node useful"),
        ],
        version="3.1",
    )


def test_apply_qiskit_compatibility_strips_literal_blocks() -> None:
    program = _sample_program()

    result = apply_qiskit_compatibility(
        program,
        literal_nodes={"literal_a"},
        literal_nodes_with_consumers=set(),
    )

    comments = [stmt.comment for stmt in result.statements if isinstance(stmt, CommentStatement)]
    assert "Start node literal_a" not in comments
    assert "End node literal_a" not in comments
    assert any(comment == "Start node useful" for comment in comments)


def test_postprocess_inserts_warning_for_consumed_literals() -> None:
    program = _sample_program()

    processed = postprocess(
        program,
        qiskit_compat=True,
        literal_nodes={"literal_a"},
        literal_nodes_with_consumers={"literal_a"},
    )

    assert isinstance(processed.statements[0], CommentStatement)
    assert "literal_a" in processed.statements[0].comment

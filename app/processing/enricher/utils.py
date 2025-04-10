from openqasm3.ast import (
    AliasStatement,
    Annotation,
    Concatenation,
    Identifier,
    IntegerLiteral,
    Pragma,
    Program,
    QubitDeclaration,
    Statement,
)

from app.model.CompileRequest import ImplementationNode, Node
from app.openqasm3.printer import leqo_dumps


def implementation(
    node: Node, statements: list[Statement | Pragma]
) -> ImplementationNode:
    program = Program(statements, version="3.1")
    return ImplementationNode(id=node.id, implementation=leqo_dumps(program))


def leqo_input(name: str, index: int, size: int) -> QubitDeclaration:
    result = QubitDeclaration(Identifier(name), IntegerLiteral(size))
    result.annotations = [Annotation("leqo.input", f"{index}")]
    return result


def leqo_output(
    name: str, index: int, value: Concatenation | Identifier
) -> AliasStatement:
    result = AliasStatement(Identifier(name), value)
    result.annotations = [Annotation("leqo.output", f"{index}")]
    return result

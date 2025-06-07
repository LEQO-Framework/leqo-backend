"""
Utils for generating implementations for a :class:`~app.model.CompileRequest.Node` in an :class:`~app.enricher.EnricherStrategy`.
"""

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

from app.enricher import ParsedImplementationNode
from app.model.CompileRequest import Node


def implementation(
    node: Node, statements: list[Statement | Pragma]
) -> ParsedImplementationNode:
    """
    Creates an :class:`~app.model.CompileRequest.ImplementationNode` from partial syntax tree.

    :param node: Node that should be enriched
    :param statements: Implementation as list of :class:`openqasm3.ast.Statement`
    """

    program = Program(statements, version="3.1")
    return ParsedImplementationNode(id=node.id, implementation=program)


def leqo_input(name: str, index: int, size: int) -> QubitDeclaration:
    """
    Creates a qubit input declaration.

    :param name: Identifier of the input declaration
    :param index: Index of the input
    :param size: Size of the input (in qubits)
    """

    result = QubitDeclaration(Identifier(name), IntegerLiteral(size))
    result.annotations = [Annotation("leqo.input", f"{index}")]
    return result


def leqo_output(
    name: str, index: int, value: Concatenation | Identifier
) -> AliasStatement:
    """
    Creates an output declaration.

    :param name: Identifier of the output declaration
    :param index: Index of the output
    :param value: Openqasm3 construct that should be the output
    """

    result = AliasStatement(Identifier(name), value)
    result.annotations = [Annotation("leqo.output", f"{index}")]
    return result

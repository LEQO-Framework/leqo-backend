"""
Utils for generating implementations for a :class:`~app.model.CompileRequest.Node` in an :class:`~app.enricher.EnricherStrategy`.
"""

from collections.abc import Sequence
from typing import cast

from openqasm3.ast import (
    AliasStatement,
    Annotation,
    Concatenation,
    Identifier,
    IndexExpression,
    IntegerLiteral,
    Pragma,
    Program,
    QubitDeclaration,
    Statement,
)

from app.enricher import ParsedImplementationNode
from app.model.CompileRequest import Node


def implementation(
    node: Node, statements: Sequence[Statement | Pragma]
) -> ParsedImplementationNode:
    """
    Creates an :class:`~app.model.CompileRequest.ImplementationNode` from partial syntax tree.

    :param node: Node that should be enriched
    :param statements: Implementation as list of :class:`openqasm3.ast.Statement`
    """

    program = Program(list(statements), version="3.1")
    return ParsedImplementationNode(id=node.id, implementation=program)


def leqo_input(
    name: str,
    index: int,
    size: int | None,
    *,
    twos_complement: bool = False,
) -> QubitDeclaration:
    """
    Creates a qubit input declaration.

    :param name: Identifier of the input declaration
    :param index: Index of the input
    :param size: Size of the input (in qubits)
    :param twos_complement: Whether the input is interpreted as two's complement.
    """

    result = QubitDeclaration(
        Identifier(name), None if size is None else IntegerLiteral(size)
    )
    result.annotations = [Annotation("leqo.input", f"{index}")]
    if twos_complement:
        result.annotations.append(Annotation("leqo.twos_complement", "true"))
    return result


AliasableExpression = Concatenation | Identifier | IndexExpression


def leqo_output(name: str, index: int, value: AliasableExpression) -> AliasStatement:
    """
    Creates an output declaration.

    :param name: Identifier of the output declaration
    :param index: Index of the output
    :param value: Openqasm3 construct that should be the output
    """

    alias_value = cast(Concatenation | Identifier, value)
    result = AliasStatement(Identifier(name), alias_value)
    result.annotations = [Annotation("leqo.output", f"{index}")]
    return result

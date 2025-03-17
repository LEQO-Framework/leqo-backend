from typing import TypeVar

from openqasm3.ast import Annotation, Expression, IntegerLiteral, Statement


def get_int(expression: Expression | None) -> int | None:
    """
    Tries to get an integer from an expression.
    This method does no analysis of the overall ast.
    If it cannot extract an integer from an expression, it throws.

    :param expression: Expression to be analyses
    :return: Integer or None if input was None
    """

    match expression:
        case None:
            return 0
        case IntegerLiteral():
            return expression.value
        case _:
            raise Exception("Invalid size")


TQasmStatement = TypeVar("TQasmStatement", bound=Statement)


def annotate(node: TQasmStatement, annotations: list[Annotation]) -> TQasmStatement:
    node.annotations = annotations
    return node

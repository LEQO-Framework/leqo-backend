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


def parse_io_annotation(annotation: Annotation) -> list[int]:
    """
    Parses the :attr:`~openqasm3.ast.Annotation.command` of a `@leqo.input` or `@leqo.output` :class:`~openqasm3.ast.Annotation`.

    :param annotation: The annotation to parse
    :return: The parsed indices
    """

    command = annotation.command and annotation.command.strip()

    if not command:
        return []

    result: list[int] = []
    for segment in command.split(","):
        range_elements = [int(x.strip()) for x in segment.split("-")]
        match len(range_elements):
            case 0:
                raise ValueError("Detected empty segment")

            case 1:
                result.append(range_elements[0])

            case 2:
                if range_elements[0] > range_elements[1]:
                    raise ValueError("Start of range must be <= end of range")

                result.extend(range(range_elements[0], range_elements[1] + 1))

            case _:
                raise ValueError("A range may only contain 2 integers")

    return result

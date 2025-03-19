from typing import TypeVar

from openqasm3.ast import (
    Annotation,
    DiscreteSet,
    Expression,
    IndexElement,
    IntegerLiteral,
    RangeDefinition,
    Statement,
    UnaryExpression,
)


def get_int(expr: Expression | None) -> int:
    """Tries to get an integer from an expression.
    This method does no analysis of the overall ast.
    If it cannot extract an integer from an expression, it throws.

    :param expression: Expression to be analyses
    :return: Integer or None if input was None
    """
    match expr:
        case None:
            return 0
        case IntegerLiteral():
            return expr.value
        case UnaryExpression():
            op = expr.op
            match op.name:
                case "-":
                    return -get_int(expr.expression)
                case _:
                    msg = f"Unsported op: {op=}"
                    raise TypeError(msg)

        case _:
            msg = f"Unsported type: {type(expr)=} of {expr=}"
            raise TypeError(msg)


TQasmStatement = TypeVar("TQasmStatement", bound=Statement)


def annotate(node: TQasmStatement, annotations: list[Annotation]) -> TQasmStatement:
    node.annotations = annotations
    return node


def parse_io_annotation(annotation: Annotation) -> list[int]:
    """Parses the :attr:`~openqasm3.ast.Annotation.command` of a `@leqo.input` or `@leqo.output` :class:`~openqasm3.ast.Annotation`.

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


def parse_range_definition(range_def: RangeDefinition, length: int) -> list[int]:
    start = get_int(range_def.start) if range_def.start is not None else 0
    end = get_int(range_def.end) if range_def.end is not None else length
    step = get_int(range_def.step) if range_def.step is not None else 1
    if start < 0:
        start = length + start
    if end < 0:
        end = length + end
    if step < 0:
        end -= 1
    else:
        end += 1
    return list(range(start, end, step))


def parse_qasm_index(index: IndexElement, length: int) -> list[int]:
    match index:
        case DiscreteSet():
            return [get_int(expr) for expr in index.values]
        case list():
            result: list[int] = []
            for v in index[
                0
            ]:  # there is a bug in openqasm3 parser, random list in list
                match v:
                    case Expression():
                        result.append(get_int(v))
                    case RangeDefinition():
                        result.extend(parse_range_definition(v, length))
            return result

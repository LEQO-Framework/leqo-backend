"""
Utils used within :mod:`app.processing`.
"""

import re
from typing import TypeVar

from openqasm3.ast import (
    Annotation,
    DiscreteSet,
    Expression,
    IndexElement,
    IntegerLiteral,
    Program,
    QASMNode,
    RangeDefinition,
    Statement,
    UnaryExpression,
)

REMOVE_INDENT = re.compile(r"\n +", re.MULTILINE)


def normalize_qasm_string(program: str) -> str:
    """Normalize QASM-string."""
    return REMOVE_INDENT.sub("\n", program).strip()


def cast_to_program(node: QASMNode | None) -> Program:
    """Cast to Program or raise error."""
    if not isinstance(node, Program):
        msg = f"Tried to cast {type(node)} to Program."
        raise TypeError(msg)
    return node


def expr_to_int(expr: Expression | None) -> int:
    """Get an integer from an expression.

    This method does no analysis of the overall AST.
    If it cannot extract an integer from an expression, it throws.

    :param expr: Expression to be analyses
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
                    return -expr_to_int(expr.expression)
                case _:
                    msg = f"Unsported op: {op=}"
                    raise TypeError(msg)

        case _:
            msg = f"Unsported type: {type(expr)=} of {expr=}"
            raise TypeError(msg)


TQasmStatement = TypeVar("TQasmStatement", bound=Statement)


def annotate(
    statement: TQasmStatement, annotations: list[Annotation]
) -> TQasmStatement:
    """
    Sets annotations on the specified node.

    :param statement: The statement to be annotated
    :param annotations: The annotations to be applied
    :return: The node with annotations applied
    """

    statement.annotations = annotations
    return statement


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
    """Return list of integers expressed by qasm3-range.

    The complexity of this function arises because openqasm3 includes the last element
    and python does not.
    """
    start = expr_to_int(range_def.start) if range_def.start is not None else 0
    end = expr_to_int(range_def.end) if range_def.end is not None else -1
    step = expr_to_int(range_def.step) if range_def.step is not None else 1
    if start < 0:
        start = length + start
    if end < 0:
        end = length + end
    if step < 0:
        end -= 1
    else:
        end += 1
    return list(range(start, end, step))


def parse_qasm_index(index: list[IndexElement], length: int) -> list[int]:
    """Parse list of qasm3 indexes and returns them as a list of integers.

    Multiple indexes are applied iteratively (as qiskit also does it).
    """
    result = list(range(length))
    for subindex in index:
        match subindex:
            case DiscreteSet():
                indecies = [expr_to_int(expr) for expr in subindex.values]
                tmp = [result[i] for i in indecies]
            case list():
                if len(subindex) != 1:
                    msg = "only 1D indexers are supported"  # qiskit 1.4.2 also raises this
                    raise TypeError(msg)
                match subindex[0]:
                    case Expression():
                        tmp = [result[expr_to_int(subindex[0])]]
                    case RangeDefinition():
                        tmp = [
                            result[i]
                            for i in parse_range_definition(subindex[0], len(result))
                        ]
        result = tmp
    return result

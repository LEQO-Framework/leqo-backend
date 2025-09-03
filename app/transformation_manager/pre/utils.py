"""
Utils used within :mod:`app.processing.pre`.
"""

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

from app.openqasm3.printer import leqo_dumps
from app.processing.frontend_graph import FrontendGraph
from app.processing.graph import ProgramGraph
from app.processing.utils import ProcessingException


class PreprocessingException(ProcessingException):
    """
    Exception raises during :mod:`app.processing.pre`.
    """


def expr_to_int(expr: Expression | None) -> int:
    """
    Get an integer from an expression.

    This method does no analysis of the overall AST.
    If it cannot extract an integer from an expression, it throws.

    :param expr: Expression to be analyses
    :return: the resulting integer parsed from the Expression
    """
    match expr:
        case IntegerLiteral():
            return expr.value
        case UnaryExpression():
            op = expr.op
            match op.name:
                case "-":
                    return -expr_to_int(expr.expression)
                case _:
                    msg = f"Unsported op: {op=}"
                    raise PreprocessingException(msg)

        case _:
            msg = f"Could not resolve {expr=} of type {type(expr)=} to an integer"
            raise PreprocessingException(msg)


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


def parse_io_annotation(annotation: Annotation) -> int:
    """
    Parse the :attr:`~openqasm3.ast.Annotation.command` of a `@leqo.input` or `@leqo.output` :class:`~openqasm3.ast.Annotation`.

    :param annotation: The annotation to parse
    :return: The indices
    """
    command = annotation.command and annotation.command.strip()

    if not command:
        msg = f"Annotation of type {type(annotation).__qualname__} without index was found."
        raise PreprocessingException(msg)

    return int(command)


def parse_range_definition(range_def: RangeDefinition, length: int) -> list[int]:
    """
    Return list of integers expressed by qasm3-range.

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


def parse_qasm_index(index: list[IndexElement], length: int) -> list[int] | int:
    """
    Parse list of qasm3 indexes.

    This can return either a single index or a subset of them.
    Multiple indexes are applied iteratively (as qiskit also does it).
    """
    result: list[int] | int = list(range(length))
    tmp: list[int] | int
    for subindex in index:
        if not isinstance(result, list):
            msg = "Unsupported: Can't further index single instance."
            raise PreprocessingException(msg)
        match subindex:
            case DiscreteSet():
                indecies = [expr_to_int(expr) for expr in subindex.values]
                tmp = [result[i] for i in indecies]
            case list():
                if len(subindex) != 1:
                    msg = "only 1D indexers are supported"  # qiskit 1.4.2 also raises this
                    raise PreprocessingException(msg)
                match subindex[0]:
                    case Expression():
                        tmp = result[expr_to_int(subindex[0])]
                    case RangeDefinition():
                        tmp = [
                            result[i]
                            for i in parse_range_definition(subindex[0], len(result))
                        ]
        result = tmp
    return result


def print_program_graph(graph: ProgramGraph) -> None:
    print("\n=== Nodes ===")
    node_index = {}
    for i, node in enumerate(graph.nodes):
        node_index[node] = i
        print(f"== Node {i} ==")
        print(leqo_dumps(graph.node_data[node].implementation))

    print("\n=== Edges ===")
    for source, target in graph.edges:
        i, j = node_index[source], node_index[target]
        print(f"== Edge {i} -> {j} ==")
        print(graph.edge_data[(source, target)])


def print_frontend_graph(graph: FrontendGraph) -> None:
    print("\n=== Nodes ===")
    node_index = {}
    for i, node in enumerate(graph.nodes):
        node_index[node] = i
        print(f"Node {i}: {node} with {graph.node_data[node]}")

    print("\n=== Edges ===")
    for source, target in graph.edges:
        i, j = node_index[source], node_index[target]
        print(f"== Edge {i} -> {j} ==")
        print(graph.edge_data[(source, target)])

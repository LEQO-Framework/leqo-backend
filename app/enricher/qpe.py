"""
Provides enricher strategy for :class:`~app.model.CompileRequest.QPENode`.
"""

from math import pi
from typing import override

from openqasm3.ast import (
    FloatLiteral,
    Identifier,
    Include,
    IndexedIdentifier,
    IntegerLiteral,
    QuantumGate,
    QubitDeclaration,
    Statement,
)

from app.enricher import (
    Constraints,
    EnricherStrategy,
    EnrichmentResult,
    ImplementationMetaData,
)
from app.enricher.exceptions import EnricherException
from app.enricher.utils import implementation, leqo_input, leqo_output
from app.model.CompileRequest import Node as FrontendNode
from app.model.CompileRequest import QPENode
from app.model.data_types import QubitType
from app.model.exceptions import InputCountMismatch, InputTypeMismatch


def _estimation(index: int) -> IndexedIdentifier:
    return IndexedIdentifier(Identifier("estimation"), [[IntegerLiteral(index)]])


def _target(index: int) -> IndexedIdentifier:
    return IndexedIdentifier(Identifier("target"), [[IntegerLiteral(index)]])


def _h(qubit: IndexedIdentifier) -> QuantumGate:
    return QuantumGate(
        modifiers=[],
        name=Identifier("h"),
        arguments=[],
        qubits=[qubit],
        duration=None,
    )


def _cp(
    angle: float, control: IndexedIdentifier, target: IndexedIdentifier
) -> QuantumGate:
    return QuantumGate(
        modifiers=[],
        name=Identifier("cp"),
        arguments=[FloatLiteral(angle)],
        qubits=[control, target],
        duration=None,
    )


def _swap(left: IndexedIdentifier, right: IndexedIdentifier) -> QuantumGate:
    return QuantumGate(
        modifiers=[],
        name=Identifier("swap"),
        arguments=[],
        qubits=[left, right],
        duration=None,
    )


def _build_inverse_qft_statements(size: int) -> list[Statement]:
    statements: list[Statement] = []

    for left in range(size // 2):
        right = size - left - 1
        statements.append(_swap(_estimation(left), _estimation(right)))

    for target in reversed(range(size)):
        for control in reversed(range(target + 1, size)):
            angle = -pi / (2 ** (control - target))
            statements.append(_cp(angle, _estimation(control), _estimation(target)))

        statements.append(_h(_estimation(target)))

    return statements


def _validate_qpe_constraints(
    constraints: Constraints | None,
    node: QPENode,
) -> None:
    if constraints is None or len(constraints.requested_inputs) != 1:
        raise InputCountMismatch(
            node,
            actual=len(constraints.requested_inputs) if constraints else 0,
            should_be="equal",
            expected=1,
        )

    input_type = constraints.requested_inputs.get(0)
    if not isinstance(input_type, QubitType):
        raise InputTypeMismatch(node, 0, actual=input_type, expected="qubit")

    if input_type.size is None:
        msg = "Could not determine size of QPE target register"
        raise EnricherException(msg, node)

    if input_type.size != 1:
        msg = "QPE V1 expects a single-qubit target register"
        raise EnricherException(msg, node)


def _build_qpe_statements(node: QPENode) -> list[Statement]:
    estimation_size = node.estimationSize

    statements: list[Statement] = [
        Include("stdgates.inc"),
        leqo_input("target", 0, 1),
        QubitDeclaration(Identifier("estimation"), IntegerLiteral(estimation_size)),
    ]

    statements.extend(_h(_estimation(index)) for index in range(estimation_size))

    for index in range(estimation_size):
        power = 2 ** (estimation_size - index - 1)
        angle = 2 * pi * node.phase * power
        statements.append(_cp(angle, _estimation(index), _target(0)))

    statements.extend(_build_inverse_qft_statements(estimation_size))

    statements.append(leqo_output("phase", 0, Identifier("estimation")))
    statements.append(leqo_output("target_out", 1, Identifier("target")))

    return statements


class QPEEnricherStrategy(EnricherStrategy):
    """
    Enricher strategy capable of enriching QPE nodes.
    """

    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> EnrichmentResult | list[EnrichmentResult]:
        match node:
            case QPENode():
                return self._enrich_qpe(node, constraints)
            case _:
                return []

    def _enrich_qpe(
        self, node: QPENode, constraints: Constraints | None
    ) -> EnrichmentResult:
        _validate_qpe_constraints(constraints, node)
        statements = _build_qpe_statements(node)

        return EnrichmentResult(
            implementation(node, statements),
            ImplementationMetaData(width=node.estimationSize, depth=None),
        )

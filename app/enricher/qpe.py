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
from app.enricher.qft import _build_qft_statements
from app.enricher.utils import implementation, leqo_input, leqo_output
from app.model.CompileRequest import Node as FrontendNode
from app.model.CompileRequest import QPENode
from app.model.data_types import QubitType
from app.model.exceptions import InputCountMismatch, InputTypeMismatch

TARGET_REGISTER_SIZE = 1


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
    angle: float,
    control: IndexedIdentifier,
    target: IndexedIdentifier,
) -> QuantumGate:
    return QuantumGate(
        modifiers=[],
        name=Identifier("cp"),
        arguments=[FloatLiteral(angle)],
        qubits=[control, target],
        duration=None,
    )


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

    if input_type.size != TARGET_REGISTER_SIZE:
        msg = "QPE V1 expects a single-qubit target register"
        raise EnricherException(msg, node)


def _controlled_phase_power_angle(
    phase: float,
    estimation_size: int,
    estimation_index: int,
) -> float:
    power = 2 ** (estimation_size - estimation_index - 1)
    return 2 * pi * phase * power


def _build_qpe_statements(node: QPENode) -> list[Statement]:
    estimation_size = node.estimationSize

    statements: list[Statement] = [
        Include("stdgates.inc"),
        leqo_input("target", 0, TARGET_REGISTER_SIZE),
        QubitDeclaration(Identifier("estimation"), IntegerLiteral(estimation_size)),
    ]

    statements.extend(_h(_estimation(index)) for index in range(estimation_size))

    statements.extend(
        _cp(
            _controlled_phase_power_angle(
                node.phase,
                estimation_size,
                index,
            ),
            _estimation(index),
            _target(0),
        )
        for index in range(estimation_size)
    )

    statements.extend(
        _build_qft_statements(
            estimation_size,
            inverse=True,
            register_name="estimation",
        )
    )

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

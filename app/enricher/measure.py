"""
Provides enricher strategy for enriching :class:`~app.model.CompileRequest.MeasurementNode`.
"""

from typing import override

from openqasm3.ast import (
    Annotation,
    BitType,
    ClassicalDeclaration,
    DiscreteSet,
    Expression,
    Identifier,
    IndexedIdentifier,
    IntegerLiteral,
    QuantumGate,
    QuantumMeasurement,
)

from app.enricher import (
    Constraints,
    EnricherStrategy,
    EnrichmentResult,
    ImplementationMetaData,
)
from app.enricher.exceptions import (
    DuplicateIndices,
    IndicesOutOfRange,
    InvalidSingleQubitIndex,
)
from app.enricher.utils import implementation, leqo_input, leqo_output
from app.model.CompileRequest import (
    MeasurementNode,
)
from app.model.CompileRequest import (
    Node as FrontendNode,
)
from app.model.data_types import QubitType
from app.model.exceptions import InputCountMismatch, InputTypeMismatch
from app.utils import duplicates


def _quantum_gate(name: str, target: Identifier | IndexedIdentifier) -> QuantumGate:
    return QuantumGate(
        modifiers=[],
        name=Identifier(name),
        arguments=[],
        qubits=[target],
    )


def _basis_change_gates(
    basis: str, target: Identifier | IndexedIdentifier
) -> list[QuantumGate]:
    if basis == "X":
        return [_quantum_gate("h", target)]

    if basis == "Y":
        return [
            _quantum_gate("sdg", target),
            _quantum_gate("h", target),
        ]

    return []


class MeasurementEnricherStrategy(EnricherStrategy):
    """
    Strategy capable of enriching :class:`~app.model.CompileRequest.MeasurementNode`.
    """

    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> EnrichmentResult | list[EnrichmentResult]:
        if not isinstance(node, MeasurementNode):
            return []

        if constraints is None or len(constraints.requested_inputs) != 1:
            raise InputCountMismatch(
                node,
                actual=len(constraints.requested_inputs) if constraints else 0,
                should_be="equal",
                expected=1,
            )

        if not isinstance(constraints.requested_inputs[0], QubitType):
            raise InputTypeMismatch(
                node,
                input_index=0,
                actual=constraints.requested_inputs[0],
                expected="qubit",
            )

        requested_type = constraints.requested_inputs[0]
        input_size = requested_type.size
        is_signed = getattr(requested_type, "signed", False)
        basis = node.basis

        if input_size is None:
            if node.indices not in ([], [0]):
                raise InvalidSingleQubitIndex(node)

            measurement_target = Identifier("q")
            basis_change_gates = _basis_change_gates(basis, measurement_target)

            statements = [
                leqo_input("q", 0, input_size, twos_complement=is_signed),
                *basis_change_gates,
                ClassicalDeclaration(
                    BitType(),
                    Identifier("result"),
                    QuantumMeasurement(measurement_target),
                ),
            ]

            qubit_alias = leqo_output("qubit_out", 1, Identifier("q"))
            if is_signed:
                qubit_alias.annotations.append(
                    Annotation("leqo.twos_complement", "true")
                )

            statements.extend(
                [
                    leqo_output("out", 0, Identifier("result")),
                    qubit_alias,
                ]
            )

            return EnrichmentResult(
                implementation(
                    node,
                    statements,
                ),
                ImplementationMetaData(width=0, depth=1 + len(basis_change_gates)),
            )

        indices = node.indices if len(node.indices) > 0 else list(range(input_size))

        out_of_range_indices = [i for i in indices if i < 0 or i >= input_size]
        if any(out_of_range_indices):
            raise IndicesOutOfRange(node, out_of_range_indices, input_size)

        duplicate_indices = list(duplicates(indices))
        if len(duplicate_indices) != 0:
            raise DuplicateIndices(node, duplicate_indices)

        index_exprs: list[Expression] = [IntegerLiteral(x) for x in indices]
        output_size = len(index_exprs)

        qubit_decl = leqo_input("q", 0, input_size, twos_complement=is_signed)
        qubit_alias = leqo_output("qubit_out", 1, Identifier("q"))
        if is_signed:
            qubit_alias.annotations.append(Annotation("leqo.twos_complement", "true"))

        measurement_target = IndexedIdentifier(
            Identifier("q"), [DiscreteSet(index_exprs)]
        )
        basis_change_gates = _basis_change_gates(basis, measurement_target)

        return EnrichmentResult(
            implementation(
                node,
                [
                    qubit_decl,
                    *basis_change_gates,
                    ClassicalDeclaration(
                        BitType(IntegerLiteral(output_size)),
                        Identifier("result"),
                        QuantumMeasurement(measurement_target),
                    ),
                    leqo_output("out", 0, Identifier("result")),
                    qubit_alias,
                ],
            ),
            ImplementationMetaData(width=0, depth=1 + len(basis_change_gates)),
        )

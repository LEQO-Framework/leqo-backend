"""
Provides enricher strategy for enriching :class:`~app.model.CompileRequest.MeasurementNode`.
"""

from typing import override

from openqasm3.ast import (
    BitType,
    ClassicalDeclaration,
    DiscreteSet,
    Expression,
    Identifier,
    IndexedIdentifier,
    IntegerLiteral,
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
    NoIndices,
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
                expected=1,
            )

        if not isinstance(constraints.requested_inputs[0], QubitType):
            raise InputTypeMismatch(
                node,
                input_index=0,
                actual=constraints.requested_inputs[0],
                expected="qubit",
            )

        input_size = constraints.requested_inputs[0].size
        if input_size is None:
            if node.indices not in ([], [0]):
                raise InvalidSingleQubitIndex(node)
            return EnrichmentResult(
                implementation(
                    node,
                    [
                        leqo_input("q", 0, input_size),
                        ClassicalDeclaration(
                            BitType(),
                            Identifier("result"),
                            QuantumMeasurement(Identifier("q")),
                        ),
                        leqo_output("out", 0, Identifier("result")),
                        leqo_output("qubit_out", 1, Identifier("q")),
                    ],
                ),
                ImplementationMetaData(width=0, depth=1),
            )

        if len(node.indices) < 1:
            raise NoIndices(node)

        out_of_range_indices = [i for i in node.indices if i < 0 or i >= input_size]
        if any(out_of_range_indices):
            raise IndicesOutOfRange(node, out_of_range_indices, input_size)

        duplicate_indices = list(duplicates(node.indices))
        if len(duplicate_indices) != 0:
            raise DuplicateIndices(node, duplicate_indices)

        indices: list[Expression] = [IntegerLiteral(x) for x in node.indices]
        output_size = len(indices)

        return EnrichmentResult(
            implementation(
                node,
                [
                    leqo_input("q", 0, input_size),
                    ClassicalDeclaration(
                        BitType(IntegerLiteral(output_size)),
                        Identifier("result"),
                        QuantumMeasurement(
                            IndexedIdentifier(Identifier("q"), [DiscreteSet(indices)])
                        ),
                    ),
                    leqo_output("out", 0, Identifier("result")),
                    leqo_output("qubit_out", 1, Identifier("q")),
                ],
            ),
            ImplementationMetaData(width=0, depth=1),
        )

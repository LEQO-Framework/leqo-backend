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
    ConstraintValidationException,
    EnricherStrategy,
    EnrichmentResult,
    ImplementationMetaData,
    NodeUnsupportedException,
)
from app.enricher.utils import implementation, leqo_input, leqo_output
from app.model.CompileRequest import (
    MeasurementNode,
)
from app.model.CompileRequest import (
    Node as FrontendNode,
)
from app.model.data_types import QubitType


class MeasurementEnricherStrategy(EnricherStrategy):
    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> EnrichmentResult:
        if not isinstance(node, MeasurementNode):
            raise NodeUnsupportedException(node)

        if constraints is None or len(constraints.requested_inputs) != 1:
            raise ConstraintValidationException(
                "Measurements can only have a single input"
            )

        if not isinstance(constraints.requested_inputs[0], QubitType):
            raise ConstraintValidationException(
                "Measurements can only have a qubit input"
            )

        input_size = constraints.requested_inputs[0].reg_size

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
                ],
            ),
            ImplementationMetaData(width=0, depth=1),
        )

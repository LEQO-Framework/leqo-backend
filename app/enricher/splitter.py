"""
Provides enricher strategy for enriching :class:`~app.model.CompileRequest.SplitterNode`.
"""

from typing import override

from openqasm3.ast import (
    DiscreteSet,
    Identifier,
    IndexExpression,
    IntegerLiteral,
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
from app.model.CompileRequest import Node as FrontendNode
from app.model.CompileRequest import SplitterNode
from app.model.data_types import QubitType


class SplitterEnricherStrategy(EnricherStrategy):
    """
    Splits a quantum register input into individual qubits.
    """

    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> EnrichmentResult:
        if not isinstance(node, SplitterNode):
            raise NodeUnsupportedException(node)

        if constraints is None or len(constraints.requested_inputs) != 1:
            raise ConstraintValidationException("Splitter requires exactly one input.")

        input = constraints.requested_inputs[0]

        if not isinstance(input, QubitType):
            raise ConstraintValidationException(
                f"Invalid input type: expected QubitType, got {type(input).__name__}."
            )

        reg_size = input.reg_size

        if reg_size < 1:
            raise ConstraintValidationException(
                f"Invalid register size: {reg_size}. Must be >= 1."
            )

        if node.number_of_outputs != reg_size:
            raise ConstraintValidationException(
                f"SplitterNode.number_of_outputs ({node.number_of_outputs}) does not match input register size ({reg_size})."
            )

        stmts = []
        identifier = "splitter_input"
        stmts.append(leqo_input(identifier, 0, reg_size))
        for index in range(reg_size):
            stmts.append(
                leqo_output(  # type: ignore[arg-type]
                    f"splitter_output_{index}",
                    index,
                    IndexExpression(  # type: ignore[arg-type]
                        Identifier(identifier), DiscreteSet([IntegerLiteral(index)])
                    ),
                )
            )

        enriched_node = implementation(node, stmts)  # type: ignore[arg-type]
        metadata = ImplementationMetaData(width=reg_size, depth=0)
        return EnrichmentResult(enriched_node=enriched_node, meta_data=metadata)

"""
Provides enricher strategy for enriching :class:`~app.model.CompileRequest.MergerNode`.
"""

from typing import override

from openqasm3.ast import (
    Concatenation,
    Identifier,
    Statement,
)

from app.enricher import (
    Constraints,
    ConstraintValidationException,
    EnricherStrategy,
    EnrichmentResult,
    ImplementationMetaData,
    InputValidationException,
)
from app.enricher.utils import implementation, leqo_input, leqo_output
from app.model.CompileRequest import MergerNode
from app.model.CompileRequest import Node as FrontendNode
from app.model.data_types import QubitType


class MergerEnricherStrategy(EnricherStrategy):
    """
    Merges multiple qubits or qubit registers into a single quantum register.
    """

    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> EnrichmentResult | list[EnrichmentResult]:
        if not isinstance(node, MergerNode):
            return []

        MIN_INPUTS: int = 2
        if constraints is None or len(constraints.requested_inputs) < MIN_INPUTS:
            raise ConstraintValidationException("Merger requires at least two inputs.")

        if node.numberInputs != len(constraints.requested_inputs):
            raise ConstraintValidationException(
                f"MergerNode.numberInputs ({node.numberInputs}) does not match the amount of provided inputs ({len(constraints.requested_inputs)})."
            )

        out_size = 0
        stmts: list[Statement] = []
        concatenation: Concatenation | Identifier | None = None

        for index in range(len(constraints.requested_inputs)):
            input = constraints.requested_inputs.get(index)

            if input is None:
                raise InputValidationException("Merger does not allow empty inputs.")

            if not isinstance(input, QubitType):
                raise ConstraintValidationException(
                    f"Invalid input type at index {index}: expected QubitType, got {type(input).__name__}."
                )

            reg_size = input.reg_size

            if reg_size < 1:
                raise ConstraintValidationException(
                    f"Invalid register size at index {index}: {reg_size}. Must be >= 1."
                )

            out_size += reg_size

            identifier = f"merger_input_{index}"
            stmts.append(leqo_input(identifier, index, reg_size))

            if concatenation is None:
                concatenation = Identifier(identifier)
            else:
                concatenation = Concatenation(concatenation, Identifier(identifier))

        if out_size < 1:
            raise ConstraintValidationException(
                "Merger must produce a non-empty register."
            )

        stmts.append(leqo_output("merger_output", 0, concatenation))  # type: ignore[arg-type]

        enriched_node = implementation(node, stmts)  # type: ignore[arg-type]
        metadata = ImplementationMetaData(width=out_size, depth=0)
        return EnrichmentResult(enriched_node=enriched_node, meta_data=metadata)

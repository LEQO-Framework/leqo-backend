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
    EnricherStrategy,
    EnrichmentResult,
    ImplementationMetaData,
)
from app.enricher.utils import implementation, leqo_input, leqo_output
from app.model.CompileRequest import MergerNode
from app.model.CompileRequest import Node as FrontendNode
from app.model.data_types import QubitType
from app.model.exceptions import (
    InputCountMismatch,
    InputNull,
    InputSizeMismatch,
    InputTypeMismatch,
)


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
            raise InputCountMismatch(
                node,
                actual=len(constraints.requested_inputs) if constraints else 0,
                expected=MIN_INPUTS,
            )

        if node.numberInputs != len(constraints.requested_inputs):
            raise InputCountMismatch(
                node,
                actual=len(constraints.requested_inputs),
                expected=node.numberInputs,
            )

        out_size = 0
        stmts: list[Statement] = []
        concatenation: Concatenation | Identifier | None = None

        for index in range(len(constraints.requested_inputs)):
            input = constraints.requested_inputs.get(index)

            if input is None:
                raise InputNull(node, index)

            if not isinstance(input, QubitType):
                raise InputTypeMismatch(node, index, actual=input, expected="qubit")

            reg_size = input.size

            if reg_size is None or reg_size < 1:
                raise InputSizeMismatch(node, index, actual=reg_size or 0, expected=1)

            out_size += reg_size

            identifier = f"merger_input_{index}"
            stmts.append(leqo_input(identifier, index, reg_size))

            if concatenation is None:
                concatenation = Identifier(identifier)
            else:
                concatenation = Concatenation(concatenation, Identifier(identifier))

        if out_size < 1:
            raise InputCountMismatch(node, actual=out_size, expected=2)

        stmts.append(leqo_output("merger_output", 0, concatenation))  # type: ignore[arg-type]

        enriched_node = implementation(node, stmts)  # type: ignore[arg-type]
        metadata = ImplementationMetaData(width=out_size, depth=0)
        return EnrichmentResult(enriched_node=enriched_node, meta_data=metadata)

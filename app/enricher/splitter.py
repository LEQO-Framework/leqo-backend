"""
Provides enricher strategy for enriching :class:`~app.model.CompileRequest.SplitterNode`.
"""

from typing import override

from openqasm3.ast import (
    AliasStatement,
    DiscreteSet,
    Identifier,
    IndexExpression,
    IntegerLiteral,
    QubitDeclaration,
)

from app.enricher import (
    Constraints,
    EnricherStrategy,
    EnrichmentResult,
    ImplementationMetaData,
)
from app.enricher.utils import implementation, leqo_input, leqo_output
from app.model.CompileRequest import Node as FrontendNode
from app.model.CompileRequest import SplitterNode
from app.model.data_types import QubitType
from app.model.exceptions import (
    InputCountMismatch,
    InputSizeMismatch,
    InputTypeMismatch,
)


class SplitterEnricherStrategy(EnricherStrategy):
    """
    Splits a quantum register input into individual qubits.
    """

    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> EnrichmentResult | list[EnrichmentResult]:
        if not isinstance(node, SplitterNode):
            return []

        if constraints is None or len(constraints.requested_inputs) != 1:
            raise InputCountMismatch(
                node,
                actual=len(constraints.requested_inputs) if constraints else 0,
                should_be="equal",
                expected=1,
            )

        input = constraints.requested_inputs[0]

        if not isinstance(input, QubitType):
            raise InputTypeMismatch(node, input_index=0, actual=input, expected="qubit")

        reg_size = input.size

        if reg_size is None or reg_size < 1:
            raise InputSizeMismatch(
                node, input_index=0, actual=reg_size or 0, expected=1
            )

        if node.numberOutputs != reg_size:
            raise InputSizeMismatch(
                node, input_index=0, actual=reg_size, expected=node.numberOutputs
            )

        stmts: list[QubitDeclaration | AliasStatement] = []
        identifier = "splitter_input"
        stmts.append(leqo_input(identifier, 0, reg_size))
        stmts.extend(
            leqo_output(
                f"splitter_output_{index}",
                index,
                IndexExpression(
                    Identifier(identifier), DiscreteSet([IntegerLiteral(index)])
                ),
            )
            for index in range(reg_size)
        )

        enriched_node = implementation(node, stmts)
        metadata = ImplementationMetaData(width=reg_size, depth=0)
        return EnrichmentResult(enriched_node=enriched_node, meta_data=metadata)

from io import UnsupportedOperation
from typing import override

from openqasm3.ast import (
    AliasStatement,
    Annotation,
    ClassicalDeclaration,
    Identifier,
    IntegerLiteral,
    Pragma,
    QubitDeclaration,
    Statement,
)

from app.enricher import (
    Constraints,
    EnricherStrategy,
    EnrichmentResult,
    ImplementationMetaData,
)
from app.enricher.utils import implementation
from app.model.CompileRequest import Node as FrontendNode
from app.model.CompileRequest import PassNode
from app.model.data_types import ClassicalType, QubitType


class PassNodeEnricherStrategy(EnricherStrategy):
    @override
    def _enrich_impl(
        self,
        node: FrontendNode,
        constraints: Constraints | None,
    ) -> EnrichmentResult | list[EnrichmentResult]:
        if not isinstance(node, PassNode):
            return []

        if constraints is None:
            msg = "if-else-node requires constraints."
            raise UnsupportedOperation(msg)

        statements: list[Statement | Pragma] = []

        out_size = 0
        for index, input_type in constraints.requested_inputs.items():
            declaration_identifier = Identifier(f"pass_node_declaration_{index}")
            declaration: QubitDeclaration | ClassicalDeclaration
            match input_type:
                case QubitType():
                    out_size += input_type.reg_size
                    declaration = QubitDeclaration(
                        declaration_identifier,
                        IntegerLiteral(input_type.reg_size),
                    )
                case ClassicalType():
                    declaration = ClassicalDeclaration(
                        input_type.to_ast(),
                        declaration_identifier,
                        None,
                    )
            declaration.annotations = [Annotation("leqo.input", str(index))]
            statements.append(declaration)
            alias = AliasStatement(
                Identifier(f"pass_node_alias_{index}"), declaration_identifier
            )
            alias.annotations = [Annotation("leqo.output", str(index))]
            statements.append(alias)

        enriched_node = implementation(node, statements)  # type: ignore[arg-type]
        metadata = ImplementationMetaData(width=out_size, depth=0)
        return EnrichmentResult(enriched_node=enriched_node, meta_data=metadata)

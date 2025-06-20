"""
Provides enricher strategy for enriching literal nodes
 * :class:`~app.model.CompileRequest.QubitNode`
 * :class:`~app.model.CompileRequest.IntLiteralNode`
 * :class:`~app.model.CompileRequest.FloatLiteralNode`
 * :class:`~app.model.CompileRequest.BitLiteralNode`
 * :class:`~app.model.CompileRequest.BoolLiteralNode`
"""

from typing import override

from openqasm3.ast import (
    BitType,
    BooleanLiteral,
    BoolType,
    ClassicalDeclaration,
    FloatLiteral,
    FloatType,
    Identifier,
    IntegerLiteral,
    IntType,
    QubitDeclaration,
)

from app.enricher import (
    Constraints,
    EnricherStrategy,
    EnrichmentResult,
    ImplementationMetaData,
)
from app.enricher.utils import implementation, leqo_output
from app.model.CompileRequest import (
    BitLiteralNode,
    BoolLiteralNode,
    FloatLiteralNode,
    IntLiteralNode,
    QubitNode,
)
from app.model.CompileRequest import (
    Node as FrontendNode,
)


class LiteralEnricherStrategy(EnricherStrategy):
    """
    Enricher strategy capable of enriching literal nodes (e.g. `int`, `float`, etc).
    """

    @override
    def _enrich_impl(  # noqa PLR0911 Too many return statements
        self, node: FrontendNode, constraints: Constraints | None
    ) -> EnrichmentResult | list[EnrichmentResult]:
        if constraints is not None and len(constraints.requested_inputs) != 0:
            return []

        match node:
            case QubitNode():
                return EnrichmentResult(
                    implementation(
                        node,
                        [
                            QubitDeclaration(
                                Identifier("literal"), IntegerLiteral(node.size)
                            ),
                            leqo_output("out", 0, Identifier("literal")),
                        ],
                    ),
                    ImplementationMetaData(width=1, depth=1),
                )

            case IntLiteralNode():
                return EnrichmentResult(
                    implementation(
                        node,
                        [
                            ClassicalDeclaration(
                                IntType(IntegerLiteral(node.bitSize)),
                                Identifier("literal"),
                                IntegerLiteral(node.value),
                            ),
                            leqo_output("out", 0, Identifier("literal")),
                        ],
                    ),
                    ImplementationMetaData(width=0, depth=1),
                )

            case FloatLiteralNode():
                return EnrichmentResult(
                    implementation(
                        node,
                        [
                            ClassicalDeclaration(
                                FloatType(IntegerLiteral(node.bitSize)),
                                Identifier("literal"),
                                FloatLiteral(node.value),
                            ),
                            leqo_output("out", 0, Identifier("literal")),
                        ],
                    ),
                    ImplementationMetaData(width=0, depth=1),
                )

            case BitLiteralNode():
                return EnrichmentResult(
                    implementation(
                        node,
                        [
                            ClassicalDeclaration(
                                BitType(),
                                Identifier("literal"),
                                IntegerLiteral(1) if node.value else IntegerLiteral(0),
                            ),
                            leqo_output("out", 0, Identifier("literal")),
                        ],
                    ),
                    ImplementationMetaData(width=0, depth=1),
                )

            case BoolLiteralNode():
                return EnrichmentResult(
                    implementation(
                        node,
                        [
                            ClassicalDeclaration(
                                BoolType(),
                                Identifier("literal"),
                                BooleanLiteral(node.value),
                            ),
                            leqo_output("out", 0, Identifier("literal")),
                        ],
                    ),
                    ImplementationMetaData(width=0, depth=1),
                )
        return []

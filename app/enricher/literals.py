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
    BooleanLiteral,
    ClassicalDeclaration,
    FloatLiteral,
    Identifier,
    IntegerLiteral,
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
    ArrayLiteralNode,
    BitLiteralNode,
    BoolLiteralNode,
    FloatLiteralNode,
    IntLiteralNode,
    Node,
    QubitNode,
)
from app.model.data_types import (
    ArrayType,
    BitType,
    BoolType,
    FloatType,
    IntType,
)


class LiteralEnricherStrategy(EnricherStrategy):
    """
    Enricher strategy capable of enriching literal nodes (e.g. `int`, `float`, etc).
    """

    @override
    def _enrich_impl(  # noqa PLR0911 Too many return statements
        self, node: Node, constraints: Constraints | None
    ) -> EnrichmentResult | list[EnrichmentResult]:
        if constraints is not None and len(constraints.requested_inputs) != 0:
            return []

        match node:
            case QubitNode():
                size = node.size if node.size is not None else 1
                return EnrichmentResult(
                    implementation(
                        node,
                        [
                            QubitDeclaration(
                                Identifier("literal"), IntegerLiteral(size)
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
                                IntType(node.bitSize).to_ast(),
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
                                FloatType(node.bitSize).to_ast(),
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
                                BitType(None).to_ast(),
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
                                BoolType().to_ast(),
                                Identifier("literal"),
                                BooleanLiteral(node.value),
                            ),
                            leqo_output("out", 0, Identifier("literal")),
                        ],
                    ),
                    ImplementationMetaData(width=0, depth=1),
                )
            case ArrayLiteralNode():
                # Detect floats
                is_float = any(
                    isinstance(v, float) or (isinstance(v, str) and "." in v)
                    for v in node.values
                )

                element_bit_size = (
                    node.elementBitSize if node.elementBitSize is not None else (32 if is_float else 1)
                )

                # Create ArrayType with correct element type (no cast)
                array_type_wrapper = ArrayType.with_size(
                    size=element_bit_size,
                    length=len(node.values),
                    is_float=is_float
                )

                array_literal = array_type_wrapper.literal(node.values)

                return EnrichmentResult(
                    implementation(
                        node,
                        [
                            ClassicalDeclaration(
                                array_type_wrapper.to_ast(),
                                Identifier("literal"),
                                array_literal,
                            ),
                            leqo_output("out", 0, Identifier("literal")),
                        ],
                    ),
                    ImplementationMetaData(width=0, depth=1),
                )
        return []
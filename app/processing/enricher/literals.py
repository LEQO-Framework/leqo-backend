from io import UnsupportedOperation

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
)

from app.model.CompileRequest import (
    BitLiteralNode,
    BoolLiteralNode,
    FloatLiteralNode,
    ImplementationNode,
    IntLiteralNode,
    LiteralNode,
)
from app.processing.enricher.utils import implementation, leqo_output


def create_literal(node: LiteralNode) -> ImplementationNode:
    match node:
        case IntLiteralNode():
            return implementation(
                node,
                [
                    ClassicalDeclaration(
                        IntType(IntegerLiteral(node.bitSize)),
                        Identifier("literal"),
                        IntegerLiteral(node.value),
                    ),
                    leqo_output("out", 0, Identifier("literal")),
                ],
            )

        case FloatLiteralNode():
            return implementation(
                node,
                [
                    ClassicalDeclaration(
                        FloatType(IntegerLiteral(node.bitSize)),
                        Identifier("literal"),
                        FloatLiteral(node.value),
                    ),
                    leqo_output("out", 0, Identifier("literal")),
                ],
            )

        case BitLiteralNode():
            return implementation(
                node,
                [
                    ClassicalDeclaration(
                        BitType(),
                        Identifier("literal"),
                        IntegerLiteral(1) if node.value else IntegerLiteral(0),
                    ),
                    leqo_output("out", 0, Identifier("literal")),
                ],
            )

        case BoolLiteralNode():
            return implementation(
                node,
                [
                    ClassicalDeclaration(
                        BoolType(), Identifier("literal"), BooleanLiteral(node.value)
                    ),
                    leqo_output("out", 0, Identifier("literal")),
                ],
            )

    raise UnsupportedOperation(f"Node {type(node).__name__} is not supported")

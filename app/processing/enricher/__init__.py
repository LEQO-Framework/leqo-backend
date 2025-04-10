from io import UnsupportedOperation

from app.model.CompileRequest import (
    BitLiteralNode,
    BoolLiteralNode,
    FloatLiteralNode,
    ImplementationNode,
    IntLiteralNode,
    MeasurementNode,
    Node,
)
from app.processing.enricher.literals import create_literal
from app.processing.enricher.measure import create_measurement


def enrich(node: Node) -> ImplementationNode:
    match node:
        case ImplementationNode():
            return node

        case (
            IntLiteralNode() | FloatLiteralNode() | BitLiteralNode() | BoolLiteralNode()
        ):
            return create_literal(node)

        case MeasurementNode():
            return create_measurement(node)

    raise UnsupportedOperation(f"Unsupported node {type(node).__name__}")

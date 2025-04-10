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

from app.model.CompileRequest import ImplementationNode, MeasurementNode
from app.processing.enricher.utils import implementation, leqo_input, leqo_output


def create_measurement(node: MeasurementNode) -> ImplementationNode:
    size = len(node.indices)
    indices: list[Expression] = [IntegerLiteral(x) for x in node.indices]
    return implementation(
        node,
        [
            leqo_input("q", 0, size),
            ClassicalDeclaration(
                BitType(IntegerLiteral(len(node.indices))),
                Identifier("result"),
                QuantumMeasurement(
                    IndexedIdentifier(Identifier("q"), [DiscreteSet(indices)])
                ),
            ),
            leqo_output("out", 0, Identifier("result")),
        ],
    )

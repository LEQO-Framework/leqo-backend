from typing import override

from openqasm3.ast import (
    FloatLiteral,
    Identifier,
    Include,
    IndexedIdentifier,
    IntegerLiteral,
    QuantumGate,
    QubitDeclaration,
    Statement,
)

from app.enricher import (
    Constraints,
    EnricherStrategy,
    EnrichmentResult,
    ImplementationMetaData,
)
from app.enricher.utils import implementation, leqo_output
from app.model.CompileRequest import Node as FrontendNode, VQENode


def _get_q(q_reg: Identifier, idx: int) -> IndexedIdentifier:
    """Helper to generate indexed qubit identifiers."""
    return IndexedIdentifier(q_reg, [[IntegerLiteral(idx)]])


class VQEEnricherStrategy(EnricherStrategy):
    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> list[EnrichmentResult]:
        if not isinstance(node, VQENode):
            return []

        n = node.numQubits
        p = node.layers

        try:
            params = (
                [float(x.strip()) for x in node.parameters.split(",")]
                if node.parameters
                else []
            )
        except ValueError:
            params = []

        expected_params = n * (p + 1)
        params = (params + [0.1] * expected_params)[:expected_params]

        statements: list[Statement] = [Include("stdgates.inc")]
        q_reg = Identifier(node.outputIdentifier)

        statements.append(QubitDeclaration(q_reg, IntegerLiteral(n)))

        param_idx = 0

        # Initial Rotation Layer (Ry)
        for q in range(n):
            statements.append(
                QuantumGate(
                    modifiers=[],
                    name=Identifier("ry"),
                    arguments=[FloatLiteral(params[param_idx])],
                    qubits=[_get_q(q_reg, q)],
                )
            )
            param_idx += 1

        # Entanglement & Rotation Layers
        for layer in range(p):
            # Entanglement (Linear CX chain)
            for q in range(n - 1):
                statements.append(
                    QuantumGate(
                        modifiers=[],
                        name=Identifier("cx"),
                        arguments=[],
                        qubits=[_get_q(q_reg, q), _get_q(q_reg, q + 1)],
                    )
                )

            # Rotation block (Ry)
            for q in range(n):
                statements.append(
                    QuantumGate(
                        modifiers=[],
                        name=Identifier("ry"),
                        arguments=[FloatLiteral(params[param_idx])],
                        qubits=[_get_q(q_reg, q)],
                    )
                )
                param_idx += 1

        statements.append(leqo_output("out_0", 0, q_reg))

        return [
            EnrichmentResult(
                implementation(node, statements),
                ImplementationMetaData(width=n, depth=p * 2 + 1),
            )
        ]

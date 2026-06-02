from typing import override

from openqasm3.ast import (
    Annotation,
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
from app.model.CompileRequest import Node as FrontendNode
from app.model.CompileRequest import VQENode


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

        if node.ansatz == "HardwareEfficient":
            return self._enrich_hardware_efficient(node)

        raise ValueError(f"Ansatz '{node.ansatz}' is currently not supported.")

    def _enrich_hardware_efficient(self, node: VQENode) -> list[EnrichmentResult]:
        n = node.numQubits
        p = node.layers

        try:
            params = (
                [float(x.strip()) for x in node.parameters.split(",")]
                if node.parameters
                else []
            )
        except ValueError as exc:
            raise ValueError("Malformed parameters provided for VQE.") from exc

        expected_params = n * (p + 1)

        if len(params) > 0 and len(params) != expected_params:
            raise ValueError(
                f"Malformed parameters: Expected {expected_params} parameters for a {n}-qubit, "
                f"{p}-layer Hardware-Efficient ansatz, but got {len(params)}."
            )

        if len(params) == 0:
            # pad entirely with 0.1 if left empty
            params = [0.1] * expected_params

        statements: list[Statement] = [Include("stdgates.inc")]
        q_reg = Identifier(node.outputIdentifier)

        q_decl = QubitDeclaration(q_reg, IntegerLiteral(n))
        q_decl.annotations = []
        if node.optimizer:
            q_decl.annotations.append(Annotation("leqo.optimizer", node.optimizer))
        if node.observable:
            q_decl.annotations.append(
                Annotation("leqo.observable", f'"{node.observable}"')
            )
        statements.append(q_decl)

        param_idx = 0

        # Initial Rotation Layer (Ry)
        statements.extend(
            [
                QuantumGate(
                    modifiers=[],
                    name=Identifier("ry"),
                    arguments=[FloatLiteral(params[param_idx + q])],
                    qubits=[_get_q(q_reg, q)],
                )
                for q in range(n)
            ]
        )
        param_idx += n

        # Entanglement & Rotation Layers
        for _layer in range(p):
            # Entanglement (Linear CX chain)
            statements.extend(
                [
                    QuantumGate(
                        modifiers=[],
                        name=Identifier("cx"),
                        arguments=[],
                        qubits=[_get_q(q_reg, q), _get_q(q_reg, q + 1)],
                    )
                    for q in range(n - 1)
                ]
            )

            # Rotation block (Ry)
            statements.extend(
                [
                    QuantumGate(
                        modifiers=[],
                        name=Identifier("ry"),
                        arguments=[FloatLiteral(params[param_idx + q])],
                        qubits=[_get_q(q_reg, q)],
                    )
                    for q in range(n)
                ]
            )
            param_idx += n

        statements.append(leqo_output("out_0", 0, q_reg))
        calculated_depth = 1 + (p * n)

        return [
            EnrichmentResult(
                implementation(node, statements),
                ImplementationMetaData(width=n, depth=calculated_depth),
            )
        ]

from typing import override
from openqasm3.ast import (
    Annotation,
    FloatLiteral,
    Identifier,
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

def _get_q(q_reg: Identifier, idx: int):
    from openqasm3.ast import IndexedIdentifier
    return IndexedIdentifier(q_reg, [[IntegerLiteral(idx)]])

class VQEEnricherStrategy(EnricherStrategy):
    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> list[EnrichmentResult]:
        if not isinstance(node, VQENode):
            return []

        ansatz = node.ansatz or "HardwareEfficient"
        
        dispatch_map = {
            "HardwareEfficient": self._enrich_hardware_efficient,
        }
        
        handler = dispatch_map.get(ansatz)
        if handler is None:
            raise ValueError(f"Ansatz '{ansatz}' is currently not supported.")
            
        return handler(node)

    def _enrich_hardware_efficient(self, node: VQENode) -> list[EnrichmentResult]:
        n = node.numQubits
        p = node.layers
        q_reg = Identifier(node.outputIdentifier or "vqe_reg")
        
        expected_params = n * (p + 1)
        
        if not node.parameters or node.parameters.strip() == "":
            params = [0.1] * expected_params
        else:
            try:
                params = [float(x.strip()) for x in node.parameters.split(",")]
            except ValueError:
                raise ValueError("Malformed parameters: Contains non-numeric values.")
            
            if len(params) != expected_params:
                raise ValueError(
                    f"Malformed parameters: Expected exactly {expected_params} parameters "
                    f"for {n} qubits and {p} layers, but received {len(params)}."
                )

        statements: list[Statement] = [
            QubitDeclaration(q_reg, IntegerLiteral(n))
        ]

        if node.optimizer:
            statements.append(Annotation(keyword="leqo.optimizer", command=node.optimizer))
        if node.observable:
            statements.append(Annotation(keyword="leqo.observable", command=f'"{node.observable}"'))

        param_idx = 0

        # Initial rotation layer (Ry)
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
            # Entanglement block (Linear CX chain)
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

        if n <= 1:
            calculated_depth = 1 + p
        elif n == 2:
            calculated_depth = 1 + 2 * p
        else:
            calculated_depth = 1 + 3 * p

        return [
            EnrichmentResult(
                implementation(node, statements),
                ImplementationMetaData(width=n, depth=calculated_depth),
            )
        ]

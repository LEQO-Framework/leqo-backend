import math
from typing import override

from openqasm3.ast import (
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
from app.model.CompileRequest import GroverNode
from app.model.CompileRequest import Node as FrontendNode


class GroverAlgorithmEnricherStrategy(EnricherStrategy):
    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> list[EnrichmentResult]:
        if not isinstance(node, GroverNode):
            return []

        n = node.numQubits
        M = len(node.targetStates)
        N = 1 << n

        if node.numIterations is None:
            iterations = (
                0
                if M in {0, N}
                else max(1, round((math.pi / (4 * math.asin(math.sqrt(M / N)))) - 0.5))
            )
        else:
            iterations = node.numIterations

        statements: list[Statement] = [Include("stdgates.inc")]

        q_reg = Identifier("query")
        statements.append(QubitDeclaration(q_reg, IntegerLiteral(n)))

        all_qubits = [IndexedIdentifier(q_reg, [[IntegerLiteral(i)]]) for i in range(n)]
        target_idx = [all_qubits[-1]]
        controls = all_qubits[:-1]

        # STEP 1: Initialization
        statements.extend(
            [
                QuantumGate(
                    modifiers=[],
                    name=Identifier("h"),
                    arguments=[],
                    qubits=[q],
                    duration=None,
                )
                for q in all_qubits
            ]
        )

        # STEP 2: The Grover Loop (Oracle + Diffuser)
        for _ in range(iterations):
            # --- 2A. The Universal Oracle (Phase Mode) ---
            for target_val in node.targetStates:
                bin_str = format(target_val, f"0{n}b")

                # Apply X to '0' bits
                statements.extend(
                    [
                        QuantumGate(
                            modifiers=[],
                            name=Identifier("x"),
                            arguments=[],
                            qubits=[all_qubits[q]],
                            duration=None,
                        )
                        for q, val in enumerate(bin_str)
                        if val == "0"
                    ]
                )

                # Apply MCZ
                statements.extend(
                    [
                        QuantumGate(
                            modifiers=[],
                            name=Identifier("h"),
                            arguments=[],
                            qubits=target_idx,
                            duration=None,
                        ),
                        QuantumGate(
                            modifiers=[],
                            name=Identifier("mcx"),
                            arguments=[],
                            qubits=[*controls, *target_idx],
                            duration=None,
                        ),
                        QuantumGate(
                            modifiers=[],
                            name=Identifier("h"),
                            arguments=[],
                            qubits=target_idx,
                            duration=None,
                        ),
                    ]
                )

                # Undo X on '0' bits
                statements.extend(
                    [
                        QuantumGate(
                            modifiers=[],
                            name=Identifier("x"),
                            arguments=[],
                            qubits=[all_qubits[q]],
                            duration=None,
                        )
                        for q, val in enumerate(bin_str)
                        if val == "0"
                    ]
                )

            # --- 2B. The Grover Diffuser ---
            statements.extend(
                [
                    QuantumGate(
                        modifiers=[],
                        name=Identifier("h"),
                        arguments=[],
                        qubits=[q],
                        duration=None,
                    )
                    for q in all_qubits
                ]
            )
            statements.extend(
                [
                    QuantumGate(
                        modifiers=[],
                        name=Identifier("x"),
                        arguments=[],
                        qubits=[q],
                        duration=None,
                    )
                    for q in all_qubits
                ]
            )
            statements.extend(
                [
                    QuantumGate(
                        modifiers=[],
                        name=Identifier("h"),
                        arguments=[],
                        qubits=target_idx,
                        duration=None,
                    ),
                    QuantumGate(
                        modifiers=[],
                        name=Identifier("mcx"),
                        arguments=[],
                        qubits=[*controls, *target_idx],
                        duration=None,
                    ),
                    QuantumGate(
                        modifiers=[],
                        name=Identifier("h"),
                        arguments=[],
                        qubits=target_idx,
                        duration=None,
                    ),
                ]
            )
            statements.extend(
                [
                    QuantumGate(
                        modifiers=[],
                        name=Identifier("x"),
                        arguments=[],
                        qubits=[q],
                        duration=None,
                    )
                    for q in all_qubits
                ]
            )
            statements.extend(
                [
                    QuantumGate(
                        modifiers=[],
                        name=Identifier("h"),
                        arguments=[],
                        qubits=[q],
                        duration=None,
                    )
                    for q in all_qubits
                ]
            )

        # STEP 3: Export the result
        statements.append(leqo_output("out", 0, q_reg))

        return [
            EnrichmentResult(
                implementation(node, statements),
                ImplementationMetaData(width=n, depth=None),
            )
        ]

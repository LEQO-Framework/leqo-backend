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
from app.model.CompileRequest import DeutschJozsaNode
from app.model.CompileRequest import Node as FrontendNode


class DeutschJozsaEnricherStrategy(EnricherStrategy):
    """
    Enricher strategy capable of generating the Deutsch-Jozsa algorithm circuit.
    """

    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> list[EnrichmentResult]:

        # Guard clause: only process if it is a DJ node
        if not isinstance(node, DeutschJozsaNode):
            return []

        n = node.numQubits
        statements: list[Statement] = [Include("stdgates.inc")]

        # 1. Register Declarations
        q_reg = Identifier("query")
        t_reg = Identifier("target")

        statements.append(QubitDeclaration(q_reg, IntegerLiteral(n)))
        statements.append(QubitDeclaration(t_reg, IntegerLiteral(1)))

        # 2. Initialize Target Qubit to |-> state
        t_idx = [IndexedIdentifier(t_reg, [[IntegerLiteral(0)]])]
        statements.append(
            QuantumGate(
                modifiers=[],
                name=Identifier("x"),
                arguments=[],
                qubits=t_idx,
                duration=None,
            )
        )
        statements.append(
            QuantumGate(
                modifiers=[],
                name=Identifier("h"),
                arguments=[],
                qubits=t_idx,
                duration=None,
            )
        )

        # 3. Create Superposition on Query Qubits
        statements.extend(
            [
                QuantumGate(
                    modifiers=[],
                    name=Identifier("h"),
                    arguments=[],
                    qubits=[IndexedIdentifier(q_reg, [[IntegerLiteral(i)]])],
                    duration=None,
                )
                for i in range(n)
            ]
        )

        # 4. Apply the Oracle & Calculate Depth
        base_depth = 3  # X target, Initial H's, Final H's

        if node.oracleType == "constant":
            oracle_depth = 1 if node.constantValue == 1 else 0
            if node.constantValue == 1:
                statements.append(
                    QuantumGate(
                        modifiers=[],
                        name=Identifier("x"),
                        arguments=[],
                        qubits=t_idx,
                        duration=None,
                    )
                )
        else:
            mask = node.balancedMask
            oracle_depth = mask.bit_count()

            for i in range(n):
                # Apply CNOT if the i-th bit of the mask is 1
                if (mask >> i) & 1:
                    control_target = [
                        IndexedIdentifier(q_reg, [[IntegerLiteral(i)]]),
                        IndexedIdentifier(t_reg, [[IntegerLiteral(0)]]),
                    ]
                    statements.append(
                        QuantumGate(
                            modifiers=[],
                            name=Identifier("cx"),
                            arguments=[],
                            qubits=control_target,
                            duration=None,
                        )
                    )

        calculated_depth = base_depth + oracle_depth

        # 5. Interference
        for i in range(n):
            q_idx = [IndexedIdentifier(q_reg, [[IntegerLiteral(i)]])]
            statements.append(
                QuantumGate(
                    modifiers=[],
                    name=Identifier("h"),
                    arguments=[],
                    qubits=q_idx,
                    duration=None
                )
            )

        # 6. Expose Output
        statements.append(leqo_output("out", 0, q_reg))

        return [
            EnrichmentResult(
                implementation(node, statements),
                ImplementationMetaData(width=n + 1, depth=calculated_depth),
            )
        ]

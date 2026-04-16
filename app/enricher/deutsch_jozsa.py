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

from app.enricher import Constraints, EnricherStrategy, EnrichmentResult, ImplementationMetaData
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

        if node.oracleType == "balanced":
            mask = node.balancedMask or 1
            n = mask.bit_length()  # e.g., 13 (1101) --> 4 qubits
        else:
            n = 1  # For a constant oracle, 1 query qubit is enough
        statements: list[Statement] = [Include("stdgates.inc")]

        # 1. Register Declarations (Removed Classical Result Array)
        q_reg = Identifier("query")
        t_reg = Identifier("target")

        statements.append(QubitDeclaration(q_reg, IntegerLiteral(n)))
        statements.append(QubitDeclaration(t_reg, IntegerLiteral(1)))

        # 2. Initialize Target Qubit to |-> state
        t_idx = [IndexedIdentifier(t_reg, [[IntegerLiteral(0)]])]
        statements.append(QuantumGate(modifiers=[], name=Identifier("x"), arguments=[], qubits=t_idx, duration=None))
        statements.append(QuantumGate(modifiers=[], name=Identifier("h"), arguments=[], qubits=t_idx, duration=None))

        # 3. Create Superposition on Query Qubits
        for i in range(n):
            q_idx = [IndexedIdentifier(q_reg, [[IntegerLiteral(i)]])]
            statements.append(QuantumGate(modifiers=[], name=Identifier("h"), arguments=[], qubits=q_idx, duration=None))

        # 4. Apply the Oracle
        if node.oracleType == "constant":
            if node.constantValue == 1:
                statements.append(QuantumGate(modifiers=[], name=Identifier("x"), arguments=[], qubits=t_idx, duration=None))
        else:
            mask = node.balancedMask or 1
            for i in range(n):
                if (mask >> i) & 1:
                    control_target = [
                        IndexedIdentifier(q_reg, [[IntegerLiteral(i)]]),
                        IndexedIdentifier(t_reg, [[IntegerLiteral(0)]])
                    ]
                    statements.append(QuantumGate(modifiers=[], name=Identifier("cx"), arguments=[], qubits=control_target, duration=None))

        # 5. Interference
        for i in range(n):
            q_idx = [IndexedIdentifier(q_reg, [[IntegerLiteral(i)]])]
            statements.append(QuantumGate(modifiers=[], name=Identifier("h"), arguments=[], qubits=q_idx, duration=None))

        # 6. Expose Output (Pass the RAW quantum register to the next node!)
        statements.append(leqo_output("out", 0, q_reg))

        return [
            EnrichmentResult(
                implementation(node, statements),
                ImplementationMetaData(width=n + 1, depth=5)
            )
        ]
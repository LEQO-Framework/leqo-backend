from typing import override
from openqasm3.ast import (
    Identifier,
    Include,
    IndexedIdentifier,
    IntegerLiteral,
    QuantumGate,
    QubitDeclaration,
    Statement,
    Annotation,
)
from app.enricher import Constraints, EnricherStrategy, EnrichmentResult, ImplementationMetaData
from app.enricher.utils import implementation, leqo_output
from app.model.CompileRequest import Node as FrontendNode
from app.model.CompileRequest import UniversalOracleNode, GroverDiffuserNode

class UniversalOracleEnricherStrategy(EnricherStrategy):
    @override
    def _enrich_impl(self, node: FrontendNode, constraints: Constraints | None) -> list[EnrichmentResult]:
        if not isinstance(node, UniversalOracleNode):
            return []

        n = node.numQubits
        statements: list[Statement] = [Include("stdgates.inc")]
        
        q_reg = Identifier("query")
        q_decl = QubitDeclaration(q_reg, IntegerLiteral(n))
        q_decl.annotations = [Annotation("leqo.input", "0")]
        statements.append(q_decl)

        # If boolean mode (Deutsch-Jozsa), we need a target register
        if node.mode == "boolean":
            t_reg = Identifier("target")
            statements.append(QubitDeclaration(t_reg, IntegerLiteral(1)))
            target_idx = [IndexedIdentifier(t_reg, [[IntegerLiteral(0)]])]
        else:
            # For phase mode (Grover), the target is just the last query qubit
            target_idx = [IndexedIdentifier(q_reg, [[IntegerLiteral(n - 1)]])]

        # Build the circuit from the truth table
        for i, bit in enumerate(node.truthTable):
            if bit == '1':
                # 1. Apply X gates to qubits that are '0' in the binary representation of i
                bin_str = format(i, f'0{n}b')
                for q, val in enumerate(bin_str):
                    if val == '0':
                        q_idx = [IndexedIdentifier(q_reg, [[IntegerLiteral(q)]])]
                        statements.append(QuantumGate(modifiers=[], name=Identifier("x"), arguments=[], qubits=q_idx, duration=None))

                # 2. Apply Multi-Controlled X (MCX) or MCZ
                controls = [IndexedIdentifier(q_reg, [[IntegerLiteral(q)]]) for q in range(n) if node.mode == "boolean" or q != n-1]
                
                if node.mode == "phase":
                    # Phase mode: Apply H, then MCX, then H to the last qubit to simulate MCZ
                    statements.append(QuantumGate(modifiers=[], name=Identifier("h"), arguments=[], qubits=target_idx, duration=None))
                
                # We assume 'mcx' is available or will be transpiled by Qiskit downstream
                statements.append(QuantumGate(modifiers=[], name=Identifier("mcx"), arguments=[], qubits=[*controls, *target_idx], duration=None))
                
                if node.mode == "phase":
                    statements.append(QuantumGate(modifiers=[], name=Identifier("h"), arguments=[], qubits=target_idx, duration=None))

                # 3. Undo the X gates
                for q, val in enumerate(bin_str):
                    if val == '0':
                        q_idx = [IndexedIdentifier(q_reg, [[IntegerLiteral(q)]])]
                        statements.append(QuantumGate(modifiers=[], name=Identifier("x"), arguments=[], qubits=q_idx, duration=None))

        # Expose outputs
        statements.append(leqo_output("out", 0, q_reg))

        return [EnrichmentResult(implementation(node, statements), ImplementationMetaData(width=n + (1 if node.mode == "boolean" else 0), depth=n*3))]


class GroverDiffuserEnricherStrategy(EnricherStrategy):
    @override
    def _enrich_impl(self, node: FrontendNode, constraints: Constraints | None) -> list[EnrichmentResult]:
        if not isinstance(node, GroverDiffuserNode):
            return []

        n = node.numQubits
        statements: list[Statement] = [Include("stdgates.inc")]
        q_reg = Identifier("query")
        q_decl = QubitDeclaration(q_reg, IntegerLiteral(n))
        q_decl.annotations = [Annotation("leqo.input", "0")]
        statements.append(q_decl)

        all_qubits = [IndexedIdentifier(q_reg, [[IntegerLiteral(i)]]) for i in range(n)]
        controls = all_qubits[:-1]
        target = [all_qubits[-1]]

        # Apply H to all
        for q in all_qubits:
            statements.append(QuantumGate(modifiers=[], name=Identifier("h"), arguments=[], qubits=[q], duration=None))
        
        # Apply X to all
        for q in all_qubits:
            statements.append(QuantumGate(modifiers=[], name=Identifier("x"), arguments=[], qubits=[q], duration=None))

        # Apply MCZ (H on target, MCX on all, H on target)
        statements.append(QuantumGate(modifiers=[], name=Identifier("h"), arguments=[], qubits=target, duration=None))
        statements.append(QuantumGate(modifiers=[], name=Identifier("mcx"), arguments=[], qubits=[*controls, *target], duration=None))
        statements.append(QuantumGate(modifiers=[], name=Identifier("h"), arguments=[], qubits=target, duration=None))

        # Apply X to all
        for q in all_qubits:
            statements.append(QuantumGate(modifiers=[], name=Identifier("x"), arguments=[], qubits=[q], duration=None))

        # Apply H to all
        for q in all_qubits:
            statements.append(QuantumGate(modifiers=[], name=Identifier("h"), arguments=[], qubits=[q], duration=None))

        statements.append(leqo_output("out", 0, q_reg))

        return [EnrichmentResult(implementation(node, statements), ImplementationMetaData(width=n, depth=5))]

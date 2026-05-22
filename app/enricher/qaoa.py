import ast
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
from app.model.CompileRequest import Node as FrontendNode
from app.model.CompileRequest import QAOANode


class QAOAEnricherStrategy(EnricherStrategy):
    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> list[EnrichmentResult]:
        if not isinstance(node, QAOANode):
            return []

        try:
            edges = ast.literal_eval(node.edges)
            if edges and isinstance(edges, list) and not isinstance(edges[0], list):
                edges = [edges[i:i+2] for i in range(0, len(edges), 2)]
                
            num_qubits = max(max(edge) for edge in edges) + 1
        except Exception:
            edges = [[0, 1]]
            num_qubits = 2

        # Parse Gamma and Beta inputs
        try:
            gammas = [float(x.strip()) for x in node.gamma.split(",")] if node.gamma else []
        except ValueError:
            gammas = []
        try:
            betas = [float(x.strip()) for x in node.beta.split(",")] if node.beta else []
        except ValueError:
            betas = []
            
        # Ensure they match the number of layers 'p' by extending with the last element or defaults
        default_gamma = gammas[-1] if gammas else 0.5
        default_beta = betas[-1] if betas else 0.2

        gammas = (gammas + [default_gamma] * node.p)[:node.p]
        betas = (betas + [default_beta] * node.p)[:node.p]

        statements: list[Statement] = [Include("stdgates.inc")]
        q_reg = Identifier(node.outputIdentifier)

        # 1. Declare the Quantum Register
        statements.append(QubitDeclaration(q_reg, IntegerLiteral(num_qubits)))

        def get_q(idx: int) -> IndexedIdentifier:
            return IndexedIdentifier(q_reg, [[IntegerLiteral(idx)]])

        # 2. Initial Superposition
        for q in range(num_qubits):
            statements.append(
                QuantumGate(modifiers=[], name=Identifier("h"), arguments=[], qubits=[get_q(q)])
            )

        # 3. Apply the QAOA Layers
        for i in range(node.p):
            gamma_val = FloatLiteral(gammas[i])
            beta_val = FloatLiteral(betas[i])
            
            problem_type = getattr(node, "problem", "MaxCut")

            # COst Hamiltonian
            if problem_type == "Max2SAT":
                for u, v in edges:
                    statements.append(QuantumGate(modifiers=[], name=Identifier("rz"), arguments=[gamma_val], qubits=[get_q(u)]))
                    statements.append(QuantumGate(modifiers=[], name=Identifier("rz"), arguments=[gamma_val], qubits=[get_q(v)]))
                    
                    statements.append(QuantumGate(modifiers=[], name=Identifier("cx"), arguments=[], qubits=[get_q(u), get_q(v)]))
                    statements.append(QuantumGate(modifiers=[], name=Identifier("rz"), arguments=[gamma_val], qubits=[get_q(v)]))
                    statements.append(QuantumGate(modifiers=[], name=Identifier("cx"), arguments=[], qubits=[get_q(u), get_q(v)]))

            elif problem_type == "GraphColoring":
                neg_gamma_val = FloatLiteral(-gammas[i])
                for u, v in edges:
                    statements.append(QuantumGate(modifiers=[], name=Identifier("cx"), arguments=[], qubits=[get_q(u), get_q(v)]))
                    statements.append(QuantumGate(modifiers=[], name=Identifier("rz"), arguments=[neg_gamma_val], qubits=[get_q(v)]))
                    statements.append(QuantumGate(modifiers=[], name=Identifier("cx"), arguments=[], qubits=[get_q(u), get_q(v)]))

            else:
                # Default / MaxCut
                for u, v in edges:
                    statements.append(QuantumGate(modifiers=[], name=Identifier("cx"), arguments=[], qubits=[get_q(u), get_q(v)]))
                    statements.append(QuantumGate(modifiers=[], name=Identifier("rz"), arguments=[gamma_val], qubits=[get_q(v)]))
                    statements.append(QuantumGate(modifiers=[], name=Identifier("cx"), arguments=[], qubits=[get_q(u), get_q(v)]))

            # Mixer Hamiltonian
            for q in range(num_qubits):
                statements.append(QuantumGate(modifiers=[], name=Identifier("rx"), arguments=[beta_val], qubits=[get_q(q)]))

        # 4. Route Output
        statements.append(leqo_output("out_0", 0, q_reg))

        return [
            EnrichmentResult(
                implementation(node, statements),
                ImplementationMetaData(width=num_qubits, depth=node.p * 3 + 1),
            )
        ]

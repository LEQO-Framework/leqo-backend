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

        is_dimacs = False
        try:
            edges = ast.literal_eval(node.edges)
            if edges and isinstance(edges, list) and not isinstance(edges[0], list):
                edges = [edges[i : i + 2] for i in range(0, len(edges), 2)]

            flattened_edges = [lit for edge in edges for lit in edge]
            if any(lit < 0 for lit in flattened_edges) or (
                node.problem == "Max2SAT" and 0 not in flattened_edges and len(flattened_edges) > 0
            ):
                is_dimacs = True
                num_qubits = max(abs(lit) for lit in flattened_edges)
            else:
                num_qubits = max(flattened_edges) + 1 if flattened_edges else 2
        except Exception:
            edges = [[0, 1]]
            num_qubits = 2
            is_dimacs = False

        # Parse Gamma and Beta inputs
        try:
            gammas = (
                [float(x.strip()) for x in node.gamma.split(",")] if node.gamma else []
            )
        except ValueError:
            gammas = []
        try:
            betas = (
                [float(x.strip()) for x in node.beta.split(",")] if node.beta else []
            )
        except ValueError:
            betas = []

        # Ensure they match the number of layers 'p' by extending with the last element or defaults
        default_gamma = gammas[-1] if gammas else 0.5
        default_beta = betas[-1] if betas else 0.2

        gammas = (gammas + [default_gamma] * node.p)[: node.p]
        betas = (betas + [default_beta] * node.p)[: node.p]

        statements: list[Statement] = [Include("stdgates.inc")]
        q_reg = Identifier(node.outputIdentifier)

        # 1. Declare the Quantum Register
        statements.append(QubitDeclaration(q_reg, IntegerLiteral(num_qubits)))

        def get_q(idx: int) -> IndexedIdentifier:
            return IndexedIdentifier(q_reg, [[IntegerLiteral(idx)]])

        # 2. Initial Superposition
        statements.extend(
            [
                QuantumGate(
                    modifiers=[], name=Identifier("h"), arguments=[], qubits=[get_q(q)]
                )
                for q in range(num_qubits)
            ]
        )

        def build_max2sat_gates(
            u: int, v: int, g_val: FloatLiteral, gamma_float: float
        ) -> list[QuantumGate]:
            if is_dimacs:
                sign_u = 1 if u > 0 else -1
                sign_v = 1 if v > 0 else -1
                idx_u = abs(u) - 1
                idx_v = abs(v) - 1

                val_u = FloatLiteral(sign_u * gamma_float)
                val_v = FloatLiteral(sign_v * gamma_float)
                val_uv = FloatLiteral(sign_u * sign_v * gamma_float)
            else:
                idx_u = u
                idx_v = v
                val_u = g_val
                val_v = g_val
                val_uv = g_val

            return [
                QuantumGate(
                    modifiers=[],
                    name=Identifier("rz"),
                    arguments=[val_u],
                    qubits=[get_q(idx_u)],
                ),
                QuantumGate(
                    modifiers=[],
                    name=Identifier("rz"),
                    arguments=[val_v],
                    qubits=[get_q(idx_v)],
                ),
                QuantumGate(
                    modifiers=[],
                    name=Identifier("cx"),
                    arguments=[],
                    qubits=[get_q(idx_u), get_q(idx_v)],
                ),
                QuantumGate(
                    modifiers=[],
                    name=Identifier("rz"),
                    arguments=[val_uv],
                    qubits=[get_q(idx_v)],
                ),
                QuantumGate(
                    modifiers=[],
                    name=Identifier("cx"),
                    arguments=[],
                    qubits=[get_q(idx_u), get_q(idx_v)],
                ),
            ]

        def build_coloring_gates(
            u_node: int, v_node: int, neg_g_val: FloatLiteral
        ) -> list[QuantumGate]:
            return [
                QuantumGate(
                    modifiers=[],
                    name=Identifier("cx"),
                    arguments=[],
                    qubits=[get_q(u_node), get_q(v_node)],
                ),
                QuantumGate(
                    modifiers=[],
                    name=Identifier("rz"),
                    arguments=[neg_g_val],
                    qubits=[get_q(v_node)],
                ),
                QuantumGate(
                    modifiers=[],
                    name=Identifier("cx"),
                    arguments=[],
                    qubits=[get_q(u_node), get_q(v_node)],
                ),
            ]

        def build_maxcut_gates(
            u_node: int, v_node: int, g_val: FloatLiteral
        ) -> list[QuantumGate]:
            return [
                QuantumGate(
                    modifiers=[],
                    name=Identifier("cx"),
                    arguments=[],
                    qubits=[get_q(u_node), get_q(v_node)],
                ),
                QuantumGate(
                    modifiers=[],
                    name=Identifier("rz"),
                    arguments=[g_val],
                    qubits=[get_q(v_node)],
                ),
                QuantumGate(
                    modifiers=[],
                    name=Identifier("cx"),
                    arguments=[],
                    qubits=[get_q(u_node), get_q(v_node)],
                ),
            ]

        # 3. Apply the QAOA Layers
        for i in range(node.p):
            gamma_val = FloatLiteral(gammas[i])
            beta_val = FloatLiteral(betas[i])

            problem_type = getattr(node, "problem", "MaxCut")

            # Cost Hamiltonian
            if problem_type == "Max2SAT":
                for u, v in edges:
                    statements.extend(build_max2sat_gates(u, v, gamma_val, gammas[i]))
            elif problem_type == "GraphColoring":
                neg_gamma_val = FloatLiteral(-gammas[i])
                for u, v in edges:
                    statements.extend(build_coloring_gates(u, v, neg_gamma_val))
            else:
                # Default / MaxCut
                beta_val = FloatLiteral(2.0 * betas[i])
                for u, v in edges:
                    statements.extend(build_maxcut_gates(u, v, gamma_val))

            # Mixer Hamiltonian
            statements.extend(
                [
                    QuantumGate(
                        modifiers=[],
                        name=Identifier("rx"),
                        arguments=[beta_val],
                        qubits=[get_q(q)],
                    )
                    for q in range(num_qubits)
                ]
            )

        # 4. Route Output
        statements.append(leqo_output("out_0", 0, q_reg))

        return [
            EnrichmentResult(
                implementation(node, statements),
                ImplementationMetaData(width=num_qubits, depth=node.p * 3 + 1),
            )
        ]

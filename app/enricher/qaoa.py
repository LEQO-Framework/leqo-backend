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


def _get_q(q_reg: Identifier, idx: int) -> IndexedIdentifier:
    """Helper to generate indexed qubit identifiers."""
    return IndexedIdentifier(q_reg, [[IntegerLiteral(idx)]])


def _parse_edges(edges_str: str, problem: str) -> tuple[list[list[int]], int, bool]:
    """Extracts edges, dynamic register width, and DIMACS status."""
    try:
        edges = ast.literal_eval(edges_str)
        if edges and isinstance(edges, list) and not isinstance(edges[0], list):
            edges = [edges[i : i + 2] for i in range(0, len(edges), 2)]

        flattened_edges = [lit for edge in edges for lit in edge]
        if any(lit < 0 for lit in flattened_edges) or (
            problem == "Max2SAT"
            and 0 not in flattened_edges
            and len(flattened_edges) > 0
        ):
            is_dimacs = True
            num_qubits = max(abs(lit) for lit in flattened_edges)
        else:
            is_dimacs = False
            num_qubits = max(flattened_edges) + 1 if flattened_edges else 2
    except Exception:
        edges = [[0, 1]]
        num_qubits = 2
        is_dimacs = False
    return edges, num_qubits, is_dimacs


def _build_max2sat_gates(
    q_reg: Identifier,
    u: int,
    v: int,
    gamma_float: float,
    is_dimacs: bool,
) -> list[QuantumGate]:
    """Generates cost gates for Max-2-SAT with optional literal polarity inversion."""
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
        g_val = FloatLiteral(gamma_float)
        val_u = g_val
        val_v = g_val
        val_uv = g_val

    return [
        QuantumGate(
            modifiers=[],
            name=Identifier("rz"),
            arguments=[val_u],
            qubits=[_get_q(q_reg, idx_u)],
        ),
        QuantumGate(
            modifiers=[],
            name=Identifier("rz"),
            arguments=[val_v],
            qubits=[_get_q(q_reg, idx_v)],
        ),
        QuantumGate(
            modifiers=[],
            name=Identifier("cx"),
            arguments=[],
            qubits=[_get_q(q_reg, idx_u), _get_q(q_reg, idx_v)],
        ),
        QuantumGate(
            modifiers=[],
            name=Identifier("rz"),
            arguments=[val_uv],
            qubits=[_get_q(q_reg, idx_v)],
        ),
        QuantumGate(
            modifiers=[],
            name=Identifier("cx"),
            arguments=[],
            qubits=[_get_q(q_reg, idx_u), _get_q(q_reg, idx_v)],
        ),
    ]


def _build_coloring_gates(
    q_reg: Identifier, u_node: int, v_node: int, neg_g_val: FloatLiteral
) -> list[QuantumGate]:
    """Generates negative conflict penalty cost gates for Graph Coloring."""
    return [
        QuantumGate(
            modifiers=[],
            name=Identifier("cx"),
            arguments=[],
            qubits=[_get_q(q_reg, u_node), _get_q(q_reg, v_node)],
        ),
        QuantumGate(
            modifiers=[],
            name=Identifier("rz"),
            arguments=[neg_g_val],
            qubits=[_get_q(q_reg, v_node)],
        ),
        QuantumGate(
            modifiers=[],
            name=Identifier("cx"),
            arguments=[],
            qubits=[_get_q(q_reg, u_node), _get_q(q_reg, v_node)],
        ),
    ]


def _build_maxcut_gates(
    q_reg: Identifier, u_node: int, v_node: int, g_val: FloatLiteral
) -> list[QuantumGate]:
    """Generates standard ZZ interaction cost gates for MaxCut."""
    return [
        QuantumGate(
            modifiers=[],
            name=Identifier("cx"),
            arguments=[],
            qubits=[_get_q(q_reg, u_node), _get_q(q_reg, v_node)],
        ),
        QuantumGate(
            modifiers=[],
            name=Identifier("rz"),
            arguments=[g_val],
            qubits=[_get_q(q_reg, v_node)],
        ),
        QuantumGate(
            modifiers=[],
            name=Identifier("cx"),
            arguments=[],
            qubits=[_get_q(q_reg, u_node), _get_q(q_reg, v_node)],
        ),
    ]


class QAOAEnricherStrategy(EnricherStrategy):
    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> list[EnrichmentResult]:
        if not isinstance(node, QAOANode):
            return []

        problem_type = getattr(node, "problem", "MaxCut")
        edges, num_qubits, is_dimacs = _parse_edges(node.edges, problem_type)

        # Parse Gamma and Beta inputs
        try:
            gammas = [float(x.strip()) for x in node.gamma.split(",")] if node.gamma else []
        except ValueError:
            gammas = []
        try:
            betas = [float(x.strip()) for x in node.beta.split(",")] if node.beta else []
        except ValueError:
            betas = []

        default_gamma = gammas[-1] if gammas else 0.5
        default_beta = betas[-1] if betas else 0.2

        gammas = (gammas + [default_gamma] * node.p)[: node.p]
        betas = (betas + [default_beta] * node.p)[: node.p]

        statements: list[Statement] = [Include("stdgates.inc")]
        q_reg = Identifier(node.outputIdentifier)

        # 1. Declare the Quantum Register
        statements.append(QubitDeclaration(q_reg, IntegerLiteral(num_qubits)))

        # 2. Initial Superposition
        statements.extend(
            [
                QuantumGate(
                    modifiers=[],
                    name=Identifier("h"),
                    arguments=[],
                    qubits=[_get_q(q_reg, q)],
                )
                for q in range(num_qubits)
            ]
        )

        # 3. Apply the QAOA Layers
        for i in range(node.p):
            gamma_val = FloatLiteral(gammas[i])
            beta_val = FloatLiteral(betas[i])

            # Cost Hamiltonian
            if problem_type == "Max2SAT":
                for u, v in edges:
                    statements.extend(_build_max2sat_gates(q_reg, u, v, gammas[i], is_dimacs))
            elif problem_type == "GraphColoring":
                neg_gamma_val = FloatLiteral(-gammas[i])
                for u, v in edges:
                    statements.extend(_build_coloring_gates(q_reg, u, v, neg_gamma_val))
            else:
                # Default / MaxCut
                beta_val = FloatLiteral(2.0 * betas[i])
                for u, v in edges:
                    statements.extend(_build_maxcut_gates(q_reg, u, v, gamma_val))

            # Mixer Hamiltonian
            statements.extend(
                [
                    QuantumGate(
                        modifiers=[],
                        name=Identifier("rx"),
                        arguments=[beta_val],
                        qubits=[_get_q(q_reg, q)],
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

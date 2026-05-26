from typing import override

from openqasm3.ast import (
    Annotation,
    GateModifierName,
    Identifier,
    Include,
    IndexedIdentifier,
    IntegerLiteral,
    QuantumGate,
    QuantumGateModifier,
    QubitDeclaration,
    Statement,
)

from app.enricher import (
    Constraints,
    EnrichmentResult,
    EnricherStrategy,
    ImplementationMetaData,
)
from app.enricher.utils import implementation, leqo_output
from app.model.CompileRequest import (
    GroverDiffuserNode,
    Node as FrontendNode,
    UniversalOracleNode,
)

MAX_STANDARD_CONTROLS = 2


def _add_mcx_gates(
    statements: list[Statement],
    controls: list[IndexedIdentifier],
    target: IndexedIdentifier,
    ancillas: list[IndexedIdentifier],
) -> None:
    """Decomposes multi-controlled X gate using standard library gates."""
    if len(controls) == 1:
        statements.append(
            QuantumGate(
                modifiers=[],
                name=Identifier("cx"),
                arguments=[],
                qubits=[controls[0], target],
                duration=None,
            )
        )
    elif len(controls) == MAX_STANDARD_CONTROLS:
        statements.append(
            QuantumGate(
                modifiers=[],
                name=Identifier("ccx"),
                arguments=[],
                qubits=[controls[0], controls[1], target],
                duration=None,
            )
        )
    else:
        statements.append(
            QuantumGate(
                modifiers=[],
                name=Identifier("ccx"),
                arguments=[],
                qubits=[controls[0], controls[1], ancillas[0]],
                duration=None,
            )
        )
        for i in range(1, len(controls) - 2):
            statements.append(
                QuantumGate(
                    modifiers=[],
                    name=Identifier("ccx"),
                    arguments=[],
                    qubits=[controls[i + 1], ancillas[i - 1], ancillas[i]],
                    duration=None,
                )
            )
        statements.append(
            QuantumGate(
                modifiers=[],
                name=Identifier("ccx"),
                arguments=[],
                qubits=[controls[-1], ancillas[-1], target],
                duration=None,
            )
        )
        for i in range(len(controls) - 3, 0, -1):
            statements.append(
                QuantumGate(
                    modifiers=[],
                    name=Identifier("ccx"),
                    arguments=[],
                    qubits=[controls[i + 1], ancillas[i - 1], ancillas[i]],
                    duration=None,
                )
            )
        statements.append(
            QuantumGate(
                modifiers=[],
                name=Identifier("ccx"),
                arguments=[],
                qubits=[controls[0], controls[1], ancillas[0]],
                duration=None,
            )
        )


class UniversalOracleEnricherStrategy(EnricherStrategy):
    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> list[EnrichmentResult]:
        if not isinstance(node, UniversalOracleNode):
            return []

        n = node.numQubits
        statements: list[Statement] = [Include("stdgates.inc")]

        q_reg = Identifier("query")
        q_decl = QubitDeclaration(q_reg, IntegerLiteral(n))
        q_decl.annotations = [Annotation("leqo.input", "0")]
        statements.append(q_decl)

        target_idx = [IndexedIdentifier(q_reg, [[IntegerLiteral(n - 1)]])]

        if node.mode == "boolean":
            t_reg = Identifier("target")
            statements.append(QubitDeclaration(t_reg, IntegerLiteral(1)))
            target_idx = [IndexedIdentifier(t_reg, [[IntegerLiteral(0)]])]

        num_controls = n if node.mode == "boolean" else n - 1
        num_ancillas = max(0, num_controls - 2)

        anc_reg = Identifier("anc")
        if num_ancillas > 0:
            statements.append(QubitDeclaration(anc_reg, IntegerLiteral(num_ancillas)))

        anc_qubits = (
            [
                IndexedIdentifier(anc_reg, [[IntegerLiteral(i)]])
                for i in range(num_ancillas)
            ]
            if num_ancillas > 0
            else []
        )

        for target_val in node.targetStates:
            bin_str = format(target_val, f"0{n}b")

            statements.extend(
                [
                    QuantumGate(
                        modifiers=[],
                        name=Identifier("x"),
                        arguments=[],
                        qubits=[IndexedIdentifier(q_reg, [[IntegerLiteral(q)]])],
                        duration=None,
                    )
                    for q, val in enumerate(bin_str)
                    if val == "0"
                ]
            )

            controls = [
                IndexedIdentifier(q_reg, [[IntegerLiteral(q)]])
                for q in range(n)
                if node.mode == "boolean" or q != n - 1
            ]

            if node.mode == "phase":
                statements.append(
                    QuantumGate(
                        modifiers=[],
                        name=Identifier("h"),
                        arguments=[],
                        qubits=target_idx,
                        duration=None,
                    )
                )

            if len(controls) == 1:
                gate_name = "cx"
                gate_modifiers = []
            elif len(controls) == MAX_STANDARD_CONTROLS:
                gate_name = "ccx"
                gate_modifiers = []
            else:
                gate_name = "x"
                gate_modifiers = [
                    QuantumGateModifier(
                        GateModifierName.ctrl, IntegerLiteral(len(controls))
                    )
                ]

            statements.append(
                QuantumGate(
                    modifiers=gate_modifiers,
                    name=Identifier(gate_name),
                    arguments=[],
                    qubits=[*controls, *target_idx],
                    duration=None,
                )
            )

            if node.mode == "phase":
                statements.append(
                    QuantumGate(
                        modifiers=[],
                        name=Identifier("h"),
                        arguments=[],
                        qubits=target_idx,
                        duration=None,
                    )
                )

            statements.extend(
                [
                    QuantumGate(
                        modifiers=[],
                        name=Identifier("x"),
                        arguments=[],
                        qubits=[IndexedIdentifier(q_reg, [[IntegerLiteral(q)]])],
                        duration=None,
                    )
                    for q, val in enumerate(bin_str)
                    if val == "0"
                ]
            )

        statements.append(leqo_output("out", 0, q_reg))

        return [
            EnrichmentResult(
                implementation(node, statements),
                ImplementationMetaData(
                    width=n + (1 if node.mode == "boolean" else 0), depth=n * 3
                ),
            )
        ]


class GroverDiffuserEnricherStrategy(EnricherStrategy):
    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> list[EnrichmentResult]:
        if not isinstance(node, GroverDiffuserNode):
            return []

        n = node.numQubits
        statements: list[Statement] = [Include("stdgates.inc")]

        q_reg = Identifier("query")
        q_decl = QubitDeclaration(q_reg, IntegerLiteral(n))
        q_decl.annotations = [Annotation("leqo.input", "0")]
        statements.append(q_decl)

        all_qubits = [IndexedIdentifier(q_reg, [[IntegerLiteral(i)]]) for i in range(n)]
        target = [all_qubits[-1]]
        controls = all_qubits[:-1]

        num_ancillas = max(0, len(controls) - 2)
        anc_reg = Identifier("anc")
        if num_ancillas > 0:
            statements.append(QubitDeclaration(anc_reg, IntegerLiteral(num_ancillas)))

        anc_qubits = (
            [
                IndexedIdentifier(anc_reg, [[IntegerLiteral(i)]])
                for i in range(num_ancillas)
            ]
            if num_ancillas > 0
            else []
        )

        if len(controls) == 1:
            gate_name = "cx"
            gate_modifiers = []
        elif len(controls) == MAX_STANDARD_CONTROLS:
            gate_name = "ccx"
            gate_modifiers = []
        else:
            gate_name = "x"
            gate_modifiers = [
                QuantumGateModifier(
                    GateModifierName.ctrl, IntegerLiteral(len(controls))
                )
            ]

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

        statements.append(
            QuantumGate(
                modifiers=[],
                name=Identifier("h"),
                arguments=[],
                qubits=target,
                duration=None,
            )
        )
        _add_mcx_gates(statements, controls, target[0], anc_qubits)
        statements.append(
            QuantumGate(
                modifiers=[],
                name=Identifier("h"),
                arguments=[],
                qubits=target,
                duration=None,
            )
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

        statements.append(leqo_output("out", 0, q_reg))

        return [
            EnrichmentResult(
                implementation(node, statements),
                ImplementationMetaData(width=n, depth=5),
            )
        ]

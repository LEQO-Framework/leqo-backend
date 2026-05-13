from typing import override

from openqasm3.ast import (
    Annotation,
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
from app.model.CompileRequest import GroverDiffuserNode, UniversalOracleNode
from app.model.CompileRequest import Node as FrontendNode


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

            statements.append(
                QuantumGate(
                    modifiers=[],
                    name=Identifier("mcx"),
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

        statements.extend(
            [
                QuantumGate(modifiers=[], name=Identifier("h"), arguments=[], qubits=[q], duration=None)
                for q in all_qubits
            ]
        )

        statements.extend(
            [
                QuantumGate(modifiers=[], name=Identifier("x"), arguments=[], qubits=[q], duration=None)
                for q in all_qubits
            ]
        )

        statements.extend(
            [
                QuantumGate(modifiers=[], name=Identifier("h"), arguments=[], qubits=target, duration=None),
                QuantumGate(modifiers=[], name=Identifier("mcx"), arguments=[], qubits=[*controls, *target], duration=None),
                QuantumGate(modifiers=[], name=Identifier("h"), arguments=[], qubits=target, duration=None),
            ]
        )

        statements.extend(
            [
                QuantumGate(modifiers=[], name=Identifier("x"), arguments=[], qubits=[q], duration=None)
                for q in all_qubits
            ]
        )

        statements.extend(
            [
                QuantumGate(modifiers=[], name=Identifier("h"), arguments=[], qubits=[q], duration=None)
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

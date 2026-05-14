from typing import override

from openqasm3.ast import (
    Annotation,
    FloatLiteral,
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
    EnricherStrategy,
    EnrichmentResult,
    ImplementationMetaData,
)
from app.enricher.utils import implementation, leqo_output
from app.model.CompileRequest import MCMTGateNode
from app.model.CompileRequest import Node as FrontendNode


class MCMTGateEnricherStrategy(EnricherStrategy):
    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> list[EnrichmentResult]:
        if not isinstance(node, MCMTGateNode):
            return []

        c = node.numControls
        t = node.numTargets
        total_qubits = c + t

        statements: list[Statement] = [Include("stdgates.inc")]
        controls = []
        targets = []

        # 1. Dynamically declare each incoming wire as its own @leqo.input
        for i in range(total_qubits):
            is_ctrl = i < c
            reg_name = f"ctrl_{i}" if is_ctrl else f"target_{i - c}"
            reg_id = Identifier(reg_name)
            
            # Determine size from constraints if available, otherwise default to 1
            size = 1
            if constraints and constraints.requested_inputs and i in constraints.requested_inputs:
                inp_type = constraints.requested_inputs[i]
                if hasattr(inp_type, "size") and inp_type.size is not None:
                    size = int(inp_type.size.value if hasattr(inp_type.size, "value") else inp_type.size)

            q_decl = QubitDeclaration(reg_id, IntegerLiteral(size))
            q_decl.annotations = [Annotation("leqo.input", str(i))]
            statements.append(q_decl)

            # Map the wires for the gate operation
            if is_ctrl:
                controls.append(IndexedIdentifier(reg_id, [[IntegerLiteral(0)]]))
            else:
                targets.append(IndexedIdentifier(reg_id, [[IntegerLiteral(0)]]))

        # 2. Prepare the gate arguments and modifiers
        args = []
        if node.parameter is not None and node.baseGate in {"rx", "ry", "rz"}:
            args.append(FloatLiteral(node.parameter))

        modifiers = [QuantumGateModifier(modifier=GateModifierName.ctrl, argument=IntegerLiteral(c))]

        # 3. Apply the Multi-Controlled gate to EACH target sequentially
        for target_qubit in targets:
            statements.append(
                QuantumGate(
                    modifiers=modifiers,
                    name=Identifier(node.baseGate),
                    arguments=args,
                    qubits=[*controls, target_qubit],
                    duration=None,
                )
            )

        # 4. Declare the outputs to pass the wires forward
        for i in range(total_qubits):
            is_ctrl = i < c
            reg_name = f"ctrl_{i}" if is_ctrl else f"target_{i - c}"
            statements.append(leqo_output(f"out_{i}", i, Identifier(reg_name)))

        return [
            EnrichmentResult(
                implementation(node, statements),
                ImplementationMetaData(width=total_qubits, depth=t),
            )
        ]

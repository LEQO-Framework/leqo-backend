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
        controls_flat = []
        targets_flat = []

        # 1. Dynamically declare each incoming wire and flatten the registers
        for i in range(total_qubits):
            is_ctrl = i < c
            reg_name = f"ctrl_{i}" if is_ctrl else f"target_{i - c}"
            reg_id = Identifier(reg_name)

            # Determine size from constraints if available, otherwise default to 1
            size = 1
            if (
                constraints
                and constraints.requested_inputs
                and i in constraints.requested_inputs
            ):
                inp_type = constraints.requested_inputs[i]
                if hasattr(inp_type, "size") and inp_type.size is not None:
                    size = int(
                        inp_type.size.value
                        if hasattr(inp_type.size, "value")
                        else inp_type.size
                    )

            q_decl = QubitDeclaration(reg_id, IntegerLiteral(size))
            q_decl.annotations = [Annotation("leqo.input", str(i))]
            statements.append(q_decl)

            # Map the wires for the gate operation by flattening the register
            for q_idx in range(size):
                indexed_id = IndexedIdentifier(reg_id, [[IntegerLiteral(q_idx)]])
                if is_ctrl:
                    controls_flat.append(indexed_id)
                else:
                    targets_flat.append(indexed_id)

        # 2. Prepare the gate arguments and modifiers
        gate_name_lower = node.baseGate.lower().split('(')[0]
        args = []
        if node.parameter is not None and node.baseGate in {"rx", "ry", "rz"}:
            args.append(FloatLiteral(node.parameter))

        modifiers = [
            QuantumGateModifier(
                modifier=GateModifierName.ctrl, argument=IntegerLiteral(len(controls_flat))
            )
        ]

        # 3. Apply the Multi-Controlled gate to EACH flattened target sequentially
        statements.extend(
            [
                QuantumGate(
                    modifiers=modifiers,
                    name=Identifier(gate_name_lower),
                    arguments=args,
                    qubits=[*controls_flat, target_qubit],
                    duration=None,
                )
                for target_qubit in targets_flat
            ]
        )

        # 4. Declare the outputs to pass the wires forward
        for i in range(total_qubits):
            is_ctrl = i < c
            reg_name = f"ctrl_{i}" if is_ctrl else f"target_{i - c}"
            statements.append(leqo_output(f"out_{i}", i, Identifier(reg_name)))

        return [
            EnrichmentResult(
                implementation(node, statements),
                ImplementationMetaData(width=total_qubits, depth=len(targets_flat)),
            )
        ]

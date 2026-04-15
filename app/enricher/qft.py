"""
Provides enricher strategy for :class:`~app.model.CompileRequest.QFTNode`.
"""

from math import pi
from typing import override

from openqasm3.ast import (
    FloatLiteral,
    Identifier,
    Include,
    IndexedIdentifier,
    IntegerLiteral,
    QuantumGate,
    Statement,
)

from app.enricher import (
    Constraints,
    EnricherStrategy,
    EnrichmentResult,
    ImplementationMetaData,
)
from app.enricher.exceptions import EnricherException
from app.enricher.utils import implementation, leqo_input, leqo_output
from app.model.CompileRequest import QFTNode
from app.model.CompileRequest import (
    Node as FrontendNode,
)
from app.model.data_types import QubitType as LeqoQubitType
from app.model.exceptions import (
    InputCountMismatch,
    InputSizeMismatch,
    InputTypeMismatch,
)


def _validate_qft_constraints(
    constraints: Constraints | None, node: QFTNode
) -> int:
    """
    Validate constraints for QFT implementations.

    QFT expects exactly one qubit input register whose size matches node.size.

    :param constraints: Constraints to validate.
    :param node: QFT node the constraints are for.
    :return: Size of the input register.
    """



    #Check for exactly one input
    # if constraints is None or len(constraints.requested_inputs) != 1:
     #   raise InputCountMismatch(
       #     node,
      #      actual=len(constraints.requested_inputs) if constraints else 0,
        #    expected=1,
        

    if constraints is None or len(constraints.requested_inputs) != 1:
        raise InputCountMismatch(
            node,
            actual=len(constraints.requested_inputs) if constraints else 0,
            should_be="equal",
            expected=1,
        )

    input_type = constraints.requested_inputs.get(0)
    if input_type is None:
        msg = "Could not determine input type for QFT input 0"
        raise EnricherException(msg, node)

    if not isinstance(input_type, LeqoQubitType):
        raise InputTypeMismatch(node, 0, actual=input_type, expected="qubit")

    size = input_type.size
    if size is None:
        msg = "Could not determine size of QFT input register"
        raise EnricherException(msg, node)

    if size != node.size:
        raise InputSizeMismatch(node, 0, actual=size, expected=node.size)

    return size




 #Check for exactly one input
    # if constraints is None or len(constraints.requested_inputs) != 1:
     #   r
       #     node,
      #      actual=len(constraints.requested_inputs) if constraints else 0,
        #    ındex hınzugefügt,

def _q(index: int) -> IndexedIdentifier:
    """
    Return q[index] as an OpenQASM indexed identifier.
    """
    return IndexedIdentifier(Identifier("q"), [[IntegerLiteral(index)]])


def _build_qft_statements(size: int) -> list[Statement]:
    """
    Build the QFT gate sequence for a register q[size].

    The implementation follows the standard forward QFT pattern:
    - Hadamard on each qubit
    - Controlled phase rotations with decreasing angles
    - Final swaps to reverse qubit order
    """

    statements: list[Statement] = []

    for target in range(size):
        statements.append(
            QuantumGate(
                modifiers=[],
                name=Identifier("h"),
                arguments=[],
                qubits=[_q(target)],
                duration=None,
            )
        )


        #for control in range(target + 1, size):
           # angle = pi / (2 ** (control - target))
            #statements.append(
             #   QuantumGate(
               #     modifiers=[],
              #3      name=Identifier("cp"),
               #     arguments=[FloatLiteral(angle)],
               
          
        #    )
        #

        for control in range(target + 1, size):
            angle = pi / (2 ** (control - target))
            statements.append(
                QuantumGate(
                    modifiers=[],
                    name=Identifier("cp"),
                    arguments=[FloatLiteral(angle)],
                    qubits=[_q(control), _q(target)],
                    duration=None,
                )
            )

    for left in range(size // 2):
        right = size - left - 1
        statements.append(
            QuantumGate(
                modifiers=[],
                name=Identifier("swap"),
                arguments=[],
                qubits=[_q(left), _q(right)],
                duration=None,
            )
        )

    return statements


class QFTEnricherStrategy(EnricherStrategy):
    """
    Enricher strategy capable of enriching QFT nodes.
    """

    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> EnrichmentResult | list[EnrichmentResult]:
        match node:
            case QFTNode():
                return self._enrich_qft(node, constraints)
            case _:
                return []

    def _enrich_qft(
        self, node: QFTNode, constraints: Constraints | None
    ) -> EnrichmentResult:
        size = _validate_qft_constraints(constraints, node)
        statements = [
            Include("stdgates.inc"),
            leqo_input("q", 0, size),
            *_build_qft_statements(size),
            leqo_output("q_out", 0, Identifier("q")),
        ]


        # return EnrichmentResult(
           # implementation(node,s),
            

        return EnrichmentResult(
            implementation(node, statements),
            ImplementationMetaData(width=0, depth=None),
        )
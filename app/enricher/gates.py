"""
Provides enricher strategy for gate nodes
 * :class:`~app.model.CompileRequest.GateNode`
 * :class:`~app.model.CompileRequest.ParameterizedGateNode`
"""

from io import UnsupportedOperation
from typing import get_args, override

from openqasm3.ast import Expression, FloatLiteral, Identifier, Include, QuantumGate

from app.enricher import (
    Constraints,
    ConstraintValidationException,
    EnricherStrategy,
    EnrichmentResult,
    ImplementationMetaData,
    NodeUnsupportedException,
)
from app.enricher.utils import implementation, leqo_input, leqo_output
from app.model.CompileRequest import (
    GateNode,
    Node,
    ParameterizedGateNode,
)
from app.model.CompileRequest import (
    Node as FrontendNode,
)
from app.model.data_types import QubitType as LeqoQubitType
from app.openqasm3.stdgates import (
    OneQubitGate,
    OneQubitGateWithAngle,
    ThreeQubitGate,
    TwoQubitGate,
    TwoQubitGateWithAngle,
    TwoQubitGateWithParam,
)


def _validate_constraints(
    constraints: Constraints | None, name: str, input_count: int
) -> int | None:
    """
    Validate constraints for gate implementations.
    Ensures the constraints contain `input_count` qubit inputs with the same size.

    :param constraints: Constraints to validate.
    :param name: Name of the gate the constraints are for.
    :param input_count: Count of expected inputs.
    :return: Size of the inputs.
    """

    if constraints is None or len(constraints.requested_inputs) != input_count:
        raise ConstraintValidationException(
            f"Gate '{name}' requires {input_count} qubits"
        )

    found_size = False
    size: int | None = None
    for _, input_type in constraints.requested_inputs.items():
        if not isinstance(input_type, LeqoQubitType):
            raise ConstraintValidationException("Gate may only have qubit inputs")

        if size is not None and size != input_type.size:
            raise ConstraintValidationException("Gate inputs must be of equal size")

        found_size = True
        size = input_type.size

    if not found_size:
        msg = "Could not determine size"
        raise UnsupportedOperation(msg)

    return size


def enrich_gate(
    node: Node,
    constraints: Constraints | None,
    gate_name: str,
    input_count: int,
    *arguments: Expression,
) -> EnrichmentResult:
    """
    Generate implementation for gate nodes.

    :param node: Node that defined the gate. (Used as context for errors etc.)
    :param constraints: Constraints that should be applied.
    :param gate_name: Name of the gate to generate.
    :param input_count: Count of expected inputs.
    :param arguments: Optional arguments passed to the gate.
    :return: Final enrichment result.
    """

    size = _validate_constraints(constraints, gate_name, input_count)

    return EnrichmentResult(
        implementation(
            node,
            [
                Include("stdgates.inc"),
                *(leqo_input(f"q{i}", i, size) for i in range(input_count)),
                QuantumGate(
                    modifiers=[],
                    name=Identifier(gate_name),
                    arguments=list(arguments),
                    qubits=[Identifier(f"q{i}") for i in range(input_count)],
                    duration=None,
                ),
                *(
                    leqo_output(f"q{i}_out", i, Identifier(f"q{i}"))
                    for i in range(input_count)
                ),
            ],
        ),
        ImplementationMetaData(width=0, depth=1),
    )


class GateEnricherStrategy(EnricherStrategy):
    """
    Enricher strategy capable of enriching gate nodes.
    """

    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> EnrichmentResult | list[EnrichmentResult]:
        match node:
            case GateNode():
                return self._enrich_simple_gate(node, constraints)

            case ParameterizedGateNode():
                return self._enrich_parameterized_gate(node, constraints)

            case _:
                return []

    def _enrich_simple_gate(
        self, node: GateNode, constraints: Constraints | None
    ) -> EnrichmentResult:
        """
        Generate implementation for gates without parameters.
        """

        if node.gate in get_args(OneQubitGate):
            return enrich_gate(node, constraints, node.gate, 1)

        if node.gate in get_args(TwoQubitGate):
            return enrich_gate(node, constraints, node.gate, 2)

        if node.gate in get_args(ThreeQubitGate):
            return enrich_gate(node, constraints, node.gate, 3)

        # to prevent breaking changes

        if node.gate == "cnot":
            return enrich_gate(node, constraints, "cx", 2)

        if node.gate == "toffoli":
            return enrich_gate(node, constraints, "ccx", 3)

        raise NodeUnsupportedException(node)

    def _enrich_parameterized_gate(
        self, node: ParameterizedGateNode, constraints: Constraints | None
    ) -> EnrichmentResult:
        """
        Generate implementation for gates with parameters.
        """

        if node.gate in get_args(OneQubitGateWithAngle):
            return enrich_gate(
                node, constraints, node.gate, 1, FloatLiteral(node.parameter)
            )

        if node.gate in get_args(TwoQubitGateWithAngle):
            return enrich_gate(
                node, constraints, node.gate, 2, FloatLiteral(node.parameter)
            )

        # Gates with generic params are currently handled exactly like gates with angles
        # In the future we might want to handle them different though

        if node.gate in get_args(TwoQubitGateWithParam):
            return enrich_gate(
                node, constraints, node.gate, 2, FloatLiteral(node.parameter)
            )

        raise NodeUnsupportedException(node)

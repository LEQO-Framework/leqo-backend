"""
Provides enricher strategy for gate nodes
 * :class:`~app.model.CompileRequest.GateNode`
 * :class:`~app.model.CompileRequest.ParameterizedGateNode`
"""

from typing import override

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


def _validate_constraints(
    constraints: Constraints | None, name: str, input_count: int
) -> int:
    """
    Validate constraints for gate implementations.
    Ensures the constraints contain `input_count` qubit inputs with the same size.

    :param constraints: Constraints to validate.
    :param name: Name of the gate the constraints are for.
    :param input_count: Count of expected inputs.
    :return: Size of the inputs.
    """

    if constraints is None:
        raise ConstraintValidationException(
            f"Gate '{name}' requires {input_count} qubits"
        )

    size: int | None = None
    for _, input_type in constraints.requested_inputs.items():
        if not isinstance(input_type, LeqoQubitType):
            raise ConstraintValidationException("Gate may only have qubit inputs")

        if size is not None and size != input_type.reg_size:
            raise ConstraintValidationException("Gate inputs must be of equal size")

        size = input_type.reg_size

    if size is None:
        raise ConstraintValidationException(
            f"Gate '{name}' requires {input_count} qubits"
        )

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

        match node.gate:
            case "cnot":
                return enrich_gate(node, constraints, "cx", 2)

            case "toffoli":
                return enrich_gate(node, constraints, "ccx", 3)

            case "h":
                return enrich_gate(node, constraints, "h", 1)

            case "x":
                return enrich_gate(node, constraints, "x", 1)

            case "y":
                return enrich_gate(node, constraints, "y", 1)

            case "z":
                return enrich_gate(node, constraints, "z", 1)

            case _:
                raise NodeUnsupportedException(node)

    def _enrich_parameterized_gate(
        self, node: ParameterizedGateNode, constraints: Constraints | None
    ) -> EnrichmentResult:
        """
        Generate implementation for gates with parameters.
        """

        match node.gate:
            case "rx":
                return enrich_gate(
                    node, constraints, "rx", 1, FloatLiteral(node.parameter)
                )

            case "ry":
                return enrich_gate(
                    node, constraints, "ry", 1, FloatLiteral(node.parameter)
                )

            case "rz":
                return enrich_gate(
                    node, constraints, "rz", 1, FloatLiteral(node.parameter)
                )

            case _:
                raise NodeUnsupportedException(node)

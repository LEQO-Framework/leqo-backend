"""
Provides enricher strategy for enriching :class:`~app.model.CompileRequest.MeasurementNode`.
"""

from typing import override

from openqasm3.ast import (
    Annotation,
    BitType,
    ClassicalDeclaration,
    DiscreteSet,
    Expression,
    Identifier,
    Include,
    IndexedIdentifier,
    IntegerLiteral,
    QuantumGate,
    QuantumMeasurement,
)

from app.enricher import (
    Constraints,
    EnricherStrategy,
    EnrichmentResult,
    ImplementationMetaData,
)
from app.enricher.exceptions import (
    DuplicateIndices,
    IndicesOutOfRange,
    InvalidSingleQubitIndex,
)
from app.enricher.utils import implementation, leqo_input, leqo_output
from app.model.CompileRequest import MeasurementNode
from app.model.CompileRequest import Node as FrontendNode
from app.model.data_types import QubitType
from app.model.exceptions import InputCountMismatch, InputTypeMismatch
from app.utils import duplicates

PAULI_BASES = frozenset({"I", "X", "Y", "Z"})


def _quantum_gate(name: str, target: Identifier | IndexedIdentifier) -> QuantumGate:
    return QuantumGate(
        modifiers=[],
        name=Identifier(name),
        arguments=[],
        qubits=[target],
    )


def _indexed_target(index: int) -> IndexedIdentifier:
    return IndexedIdentifier(Identifier("q"), [[IntegerLiteral(index)]])


def _basis_change_gates(
    basis: str, target: Identifier | IndexedIdentifier
) -> list[QuantumGate]:
    if basis == "X":
        return [_quantum_gate("h", target)]

    if basis == "Y":
        return [
            _quantum_gate("sdg", target),
            _quantum_gate("h", target),
        ]

    if basis in {"Z", "I"}:
        return []

    raise ValueError(f"Unsupported measurement basis '{basis}'.")


def _stdgates_include_if_needed(
    basis_change_gates: list[QuantumGate],
) -> list[Include]:
    if not basis_change_gates:
        return []

    return [Include("stdgates.inc")]


def _resolve_basis_string(basis: str, output_size: int) -> list[str]:
    normalized = basis.strip().upper()

    if not normalized or any(char not in PAULI_BASES for char in normalized):
        raise ValueError(f"Unsupported measurement basis '{basis}'.")

    if len(normalized) == 1:
        return [normalized] * output_size

    if len(normalized) == output_size:
        return list(normalized)

    raise ValueError(
        "Composite measurement basis length must either be 1 or match the "
        f"number of measured qubits. Got basis '{basis}' for {output_size} qubits."
    )


def _basis_change_gates_for_indices(
    bases: list[str], indices: list[int]
) -> list[QuantumGate]:
    gates: list[QuantumGate] = []

    for basis, index in zip(bases, indices, strict=True):
        gates.extend(_basis_change_gates(basis, _indexed_target(index)))

    return gates


class MeasurementEnricherStrategy(EnricherStrategy):
    """
    Strategy capable of enriching :class:`~app.model.CompileRequest.MeasurementNode`.
    """

    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> EnrichmentResult | list[EnrichmentResult]:
        if not isinstance(node, MeasurementNode):
            return []

        if constraints is None or len(constraints.requested_inputs) != 1:
            raise InputCountMismatch(
                node,
                actual=len(constraints.requested_inputs) if constraints else 0,
                should_be="equal",
                expected=1,
            )

        if not isinstance(constraints.requested_inputs[0], QubitType):
            raise InputTypeMismatch(
                node,
                input_index=0,
                actual=constraints.requested_inputs[0],
                expected="qubit",
            )

        requested_type = constraints.requested_inputs[0]
        input_size = requested_type.size
        is_signed = getattr(requested_type, "signed", False)
        basis_specs = node.pauliStrings or [node.basis]

        if input_size is None:
            return self._enrich_single_qubit_measurement(
                node=node,
                is_signed=is_signed,
                basis_specs=basis_specs,
            )

        indices = node.indices if len(node.indices) > 0 else list(range(input_size))

        out_of_range_indices = [i for i in indices if i < 0 or i >= input_size]
        if any(out_of_range_indices):
            raise IndicesOutOfRange(node, out_of_range_indices, input_size)

        duplicate_indices = list(duplicates(indices))
        if len(duplicate_indices) != 0:
            raise DuplicateIndices(node, duplicate_indices)

        return self._enrich_multi_qubit_measurement(
            node=node,
            input_size=input_size,
            is_signed=is_signed,
            indices=indices,
            basis_specs=basis_specs,
        )

    def _enrich_single_qubit_measurement(
        self,
        node: MeasurementNode,
        is_signed: bool,
        basis_specs: list[str],
    ) -> EnrichmentResult | list[EnrichmentResult]:
        if node.indices not in ([], [0]):
            raise InvalidSingleQubitIndex(node)

        results: list[EnrichmentResult] = []

        for basis_spec in basis_specs:
            bases = _resolve_basis_string(basis_spec, 1)
            measurement_target = Identifier("q")
            basis_change_gates = _basis_change_gates(bases[0], measurement_target)
            stdgates_include = _stdgates_include_if_needed(basis_change_gates)

            statements = [
                *stdgates_include,
                leqo_input("q", 0, None, twos_complement=is_signed),
                *basis_change_gates,
                ClassicalDeclaration(
                    BitType(),
                    Identifier("result"),
                    QuantumMeasurement(measurement_target),
                ),
            ]

            qubit_alias = leqo_output("qubit_out", 1, Identifier("q"))
            if is_signed:
                qubit_alias.annotations.append(
                    Annotation("leqo.twos_complement", "true")
                )

            statements.extend(
                [
                    leqo_output("out", 0, Identifier("result")),
                    qubit_alias,
                ]
            )

            results.append(
                EnrichmentResult(
                    implementation(node, statements),
                    ImplementationMetaData(width=0, depth=1 + len(basis_change_gates)),
                )
            )

        return results[0] if len(results) == 1 else results

    def _enrich_multi_qubit_measurement(
        self,
        node: MeasurementNode,
        input_size: int,
        is_signed: bool,
        indices: list[int],
        basis_specs: list[str],
    ) -> EnrichmentResult | list[EnrichmentResult]:
        index_exprs: list[Expression] = [IntegerLiteral(x) for x in indices]
        output_size = len(index_exprs)

        results: list[EnrichmentResult] = []

        for basis_spec in basis_specs:
            bases = _resolve_basis_string(basis_spec, output_size)
            basis_change_gates = _basis_change_gates_for_indices(bases, indices)
            stdgates_include = _stdgates_include_if_needed(basis_change_gates)

            qubit_decl = leqo_input("q", 0, input_size, twos_complement=is_signed)
            qubit_alias = leqo_output("qubit_out", 1, Identifier("q"))
            if is_signed:
                qubit_alias.annotations.append(
                    Annotation("leqo.twos_complement", "true")
                )

            measurement_target = IndexedIdentifier(
                Identifier("q"), [DiscreteSet(index_exprs)]
            )

            results.append(
                EnrichmentResult(
                    implementation(
                        node,
                        [
                            *stdgates_include,
                            qubit_decl,
                            *basis_change_gates,
                            ClassicalDeclaration(
                                BitType(IntegerLiteral(output_size)),
                                Identifier("result"),
                                QuantumMeasurement(measurement_target),
                            ),
                            leqo_output("out", 0, Identifier("result")),
                            qubit_alias,
                        ],
                    ),
                    ImplementationMetaData(width=0, depth=1 + len(basis_change_gates)),
                )
            )

        return results[0] if len(results) == 1 else results

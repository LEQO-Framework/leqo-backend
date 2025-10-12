"""
Provides enricher strategy for enriching :class:`~app.model.CompileRequest.EncodeValueNode` from a database.
"""

from math import pi
from typing import cast, override

from openqasm3.ast import (
    Annotation,
    BinaryExpression,
    BinaryOperator,
    BranchingStatement,
    ClassicalDeclaration,
    FloatLiteral,
    Identifier,
    Include,
    IndexedIdentifier,
    IntegerLiteral,
    QuantumGate,
    QubitDeclaration,
    Statement,
)
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.enricher import Constraints, EnrichmentResult, ImplementationMetaData
from app.enricher.db_enricher import DataBaseEnricherStrategy
from app.enricher.exceptions import BoundsOutOfRange, EncodingNotSupported
from app.enricher.models import BaseNode, EncodingType, Input, InputType, NodeType
from app.enricher.models import EncodeValueNode as EncodeNodeTable
from app.enricher.utils import implementation, leqo_output
from app.model.CompileRequest import (
    EncodeValueNode,
)
from app.model.CompileRequest import (
    Node as FrontendNode,
)
from app.model.data_types import (
    BitType,
    BoolType,
    FloatType,
    IntType,
    LeqoSupportedClassicalType,
    LeqoSupportedType,
    QubitType,
)
from app.model.exceptions import InputCountMismatch, InputSizeMismatch, InputTypeMismatch


class EncodeValueEnricherStrategy(DataBaseEnricherStrategy):
    """
    Strategy capable of enriching :class:`~app.model.CompileRequest.EncodeValueNode` from a database.
    """

    def __init__(self, engine: AsyncEngine):
        super().__init__(engine)

    def _convert_to_input_type(self, node_type: LeqoSupportedType) -> str:
        """
        Converts the node type to the enum value of :class:`~app.enricher.models.InputType`
        """
        match node_type:
            case IntType():
                input_type = InputType.IntType.value
            case FloatType():
                input_type = InputType.FloatType.value
            case BitType():
                input_type = InputType.BitType.value
            case BoolType():
                input_type = InputType.BoolType.value
            case QubitType():
                input_type = InputType.QubitType.value
            case _:
                raise RuntimeError(f"Unsupported input type: {input}")

        return input_type

    def _check_constraints(
        self, node: EncodeValueNode, requested_inputs: dict[int, LeqoSupportedType]
    ) -> None:
        """
        Checks the constraints for the node and requested inputs.
        Raises exceptions if constraints are not met.

        :param node: The node to check constraints for.
        :param requested_inputs: Dictionary where the key is the input index and value the type of the node.
        :raises EncodingNotSupported: If the encoding is not supported.
        :raises BoundsOutOfRange: If the bounds are out of range.
        :raises InputCountMismatch: If the number of requested inputs does not match the expected count.
        :raises InputTypeMismatch: If the type of the requested input does not match the expected type.
        """
        if node.encoding == "custom":
            raise EncodingNotSupported(node)

        if node.bounds < 0 or node.bounds > 1:
            raise BoundsOutOfRange(node)

        if len(requested_inputs) != 1:
            raise InputCountMismatch(
                node,
                actual=len(requested_inputs),
                should_be="equal",
                expected=1,
            )

        if not isinstance(requested_inputs[0], LeqoSupportedClassicalType):
            raise InputTypeMismatch(
                node,
                input_index=0,
                actual=requested_inputs[0],
                expected="classical",
            )

    @override
    def _generate_database_node(
        self,
        node: FrontendNode,
        implementation: str,
        requested_inputs: dict[int, LeqoSupportedType],
        width: int,
        depth: int | None,
    ) -> BaseNode | None:
        if not isinstance(node, EncodeValueNode):
            return None
        self._check_constraints(node, requested_inputs)

        converted_input_type = self._convert_to_input_type(requested_inputs[0])

        new_node = EncodeNodeTable(
            type=NodeType(node.type),
            depth=depth,
            width=width,
            implementation=implementation,
            encoding=EncodingType(node.encoding),
            bounds=node.bounds,
        )
        input_node = Input(
            index=0,
            type=converted_input_type,
            size=requested_inputs[0].size,
            )
        new_node.inputs.append(input_node)

        return new_node

    @override
    async def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> list[EnrichmentResult]:
        if isinstance(node, EncodeValueNode) and node.encoding in {"basis", "angle"}:
            # Prefer database-backed implementations first to keep behaviour consistent
            # with other encoders and reuse vetted circuits when available.
            db_results = await super()._enrich_impl(node, constraints)
            if db_results:
                return db_results

            if constraints is None:
                raise InputCountMismatch(node, actual=0, should_be="equal", expected=1)

            # On cache miss, synthesise the basis encoding implementation on the fly.
            classical_input = constraints.requested_inputs[0]
            if node.encoding == "basis":
                return [
                    self._generate_basis_enrichment(node, classical_input),
                ]
            return [
                self._generate_angle_enrichment(node, classical_input),
            ]

        return await super()._enrich_impl(node, constraints)

    @override
    def _generate_query(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> Select[tuple[BaseNode]] | None:
        if not isinstance(node, EncodeValueNode):
            return None

        if constraints is None:
            raise InputCountMismatch(
                node,
                actual=0,
                should_be="equal",
                expected=1,
            )

        self._check_constraints(node, constraints.requested_inputs)

        converted_input_type = self._convert_to_input_type(
            constraints.requested_inputs[0]
        )

        return cast(
            Select[tuple[BaseNode]],
            select(EncodeNodeTable)
            .join(Input, EncodeNodeTable.inputs)
            .where(
                EncodeNodeTable.type == NodeType(node.type),
                EncodeNodeTable.encoding == EncodingType(node.encoding),
                EncodeNodeTable.bounds == node.bounds,
                Input.index == 0,
                Input.type == converted_input_type,
                Input.size >= constraints.requested_inputs[0].size,
            ),
        )

    def _generate_basis_enrichment(
        self,
        node: EncodeValueNode,
        classical_input: LeqoSupportedClassicalType,
    ) -> EnrichmentResult:
        # The target register width is derived from the classical input type so that
        # we emit the minimum amount of qubits required for its binary representation.
        size = self._determine_register_size(node, classical_input)
        statements = self._build_basis_statements(classical_input, size)
        return EnrichmentResult(
            implementation(node, statements),
            ImplementationMetaData(width=size, depth=size),
        )

    def _generate_angle_enrichment(
        self,
        node: EncodeValueNode,
        classical_input: LeqoSupportedClassicalType,
    ) -> EnrichmentResult:
        size = self._determine_register_size(node, classical_input)
        statements = self._build_angle_statements(classical_input, size)
        return EnrichmentResult(
            implementation(node, statements),
            ImplementationMetaData(width=size, depth=size),
        )

    def _determine_register_size(
        self,
        node: EncodeValueNode,
        classical_input: LeqoSupportedClassicalType,
    ) -> int:
        match classical_input:
            case BoolType():
                size = classical_input.size
            case BitType():
                size = classical_input.size or 1
            case IntType():
                size = classical_input.size
            case FloatType():
                size = 1
            case _:
                raise InputTypeMismatch(
                    node, 0, actual=classical_input, expected="bit, int, bool or float"
                )

        if size <= 0:
            raise InputSizeMismatch(node, 0, actual=size, expected=1)

        return size

    def _build_basis_statements(
        self,
        classical_input: LeqoSupportedClassicalType,
        register_size: int,
    ) -> list[Statement]:
        value_identifier = Identifier("value")
        qubit_identifier = Identifier("encoded")

        # Declare the classical input and attach the leqo metadata so the
        # transformation pipeline understands which input feed to wire in.
        classical_decl = ClassicalDeclaration(
            classical_input.to_ast(), value_identifier, None
        )
        classical_decl.annotations = [Annotation("leqo.input", "0")]

        qubit_decl = QubitDeclaration(qubit_identifier, IntegerLiteral(register_size))

        statements: list[Statement] = [
            Include("stdgates.inc"),
            classical_decl,
            qubit_decl,
        ]

        # Flip each target qubit conditionally based on the requested basis symbol.
        for index in range(register_size):
            condition = self._bit_condition_expression(
                classical_input, value_identifier, index
            )
            target = IndexedIdentifier(
                qubit_identifier, [[IntegerLiteral(index)]]
            )
            gate = QuantumGate(
                modifiers=[],
                name=Identifier("x"),
                arguments=[],
                qubits=[target],
                duration=None,
            )
            statements.append(BranchingStatement(condition, [gate], []))

        # Expose the encoded register as the sole output of the node.
        statements.append(leqo_output("out", 0, qubit_identifier))
        return statements

    def _build_angle_statements(
        self,
        classical_input: LeqoSupportedClassicalType,
        register_size: int,
    ) -> list[Statement]:
        value_identifier = Identifier("value")
        qubit_identifier = Identifier("encoded")

        classical_decl = ClassicalDeclaration(
            classical_input.to_ast(), value_identifier, None
        )
        classical_decl.annotations = [Annotation("leqo.input", "0")]

        qubit_decl = QubitDeclaration(qubit_identifier, IntegerLiteral(register_size))

        statements: list[Statement] = [
            Include("stdgates.inc"),
            classical_decl,
            qubit_decl,
        ]

        if isinstance(classical_input, FloatType):
            rotation_gate = QuantumGate(
                modifiers=[],
                name=Identifier("ry"),
                arguments=[value_identifier],
                qubits=[qubit_identifier],
                duration=None,
            )
            statements.append(rotation_gate)
            statements.append(leqo_output("out", 0, qubit_identifier))
            return statements

        for index in range(register_size):
            condition = self._bit_condition_expression(
                classical_input, value_identifier, index
            )
            target = IndexedIdentifier(
                qubit_identifier, [[IntegerLiteral(index)]]
            )
            rotation_gate = QuantumGate(
                modifiers=[],
                name=Identifier("ry"),
                arguments=[FloatLiteral(pi)],
                qubits=[target],
                duration=None,
            )
            statements.append(BranchingStatement(condition, [rotation_gate], []))

        statements.append(leqo_output("out", 0, qubit_identifier))
        return statements

    def _bit_condition_expression(
        self,
        classical_input: LeqoSupportedClassicalType,
        value_identifier: Identifier,
        index: int,
    ) -> BinaryExpression | Identifier:
        match classical_input:
            case BoolType():
                return value_identifier
            case BitType(size=None):
                return value_identifier
            case BitType():
                element = IndexedIdentifier(
                    value_identifier, [[IntegerLiteral(index)]]
                )
                return BinaryExpression(
                    BinaryOperator["=="],
                    element,
                    IntegerLiteral(1),
                )
            case IntType():
                shifted = BinaryExpression(
                    BinaryOperator[">>"],
                    value_identifier,
                    IntegerLiteral(index),
                )
                masked = BinaryExpression(
                    BinaryOperator["&"],
                    shifted,
                    IntegerLiteral(1),
                )
                return BinaryExpression(
                    BinaryOperator["=="],
                    masked,
                    IntegerLiteral(1),
                )
            case FloatType():
                # Unsupported but handled earlier.
                raise RuntimeError("FloatType not supported for basis encoding")
            case _:
                raise RuntimeError("Unsupported classical input for basis encoding")

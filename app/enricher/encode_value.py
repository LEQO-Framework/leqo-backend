"""
Provides enricher strategy for enriching :class:`~app.model.CompileRequest.EncodeValueNode` from a database.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from math import pi, sqrt
from typing import Any, cast, override

from openqasm3 import ast
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.enricher import (
    Constraints,
    EnrichmentResult,
    ImplementationMetaData,
    models,
)
from app.enricher.db_enricher import DataBaseEnricherStrategy
from app.enricher.exceptions import BoundsOutOfRange, EncodingNotSupported
from app.enricher.utils import implementation, leqo_output
from app.model import CompileRequest, data_types
from app.model.exceptions import (
    InputCountMismatch,
    InputSizeMismatch,
    InputTypeMismatch,
)


@dataclass
class _AngleEmissionContext:
    statements: list[ast.Statement]
    qubit_identifier: ast.Identifier
    register_size: int
    rotation_map: dict[int, float] | None
    value_identifier: ast.Identifier | None


class EncodeValueEnricherStrategy(DataBaseEnricherStrategy):
    """
    Strategy capable of enriching :class:`~app.model.CompileRequest.EncodeValueNode` from a database.
    """

    def __init__(self, engine: AsyncEngine):
        super().__init__(engine)

    def _convert_to_input_type(self, node_type: data_types.LeqoSupportedType) -> str:
        """
        Converts the node type to the enum value of :class:`~app.enricher.models.InputType`
        """
        match node_type:
            case data_types.IntType():
                input_type = models.InputType.IntType.value
            case data_types.FloatType():
                input_type = models.InputType.FloatType.value
            case data_types.BitType():
                input_type = models.InputType.BitType.value
            case data_types.BoolType():
                input_type = models.InputType.BoolType.value
            case data_types.QubitType():
                input_type = models.InputType.QubitType.value
            case data_types.ArrayType():
                msg = "Unsupported input type: array"
                raise RuntimeError(msg)
            case _:
                if isinstance(node_type, ast.ArrayType):
                    msg = "Unsupported input type: array"
                    raise RuntimeError(msg)
                raise RuntimeError(f"Unsupported input type: {node_type}")

        return input_type

    def _check_constraints(
        self,
        node: CompileRequest.EncodeValueNode,
        requested_inputs: dict[int, data_types.LeqoSupportedType],
    ) -> None:
        """
        Checks the constraints for the node and requested inputs.
        Raises exceptions if constraints are not met.
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

        input_type = requested_inputs[0]
        is_classical = isinstance(
            input_type,
            (data_types.LeqoSupportedClassicalType, ast.ArrayType, ast.FloatType),
        )

        if not is_classical:
            raise InputTypeMismatch(
                node,
                input_index=0,
                actual=input_type,
                expected="classical",
            )

    @override
    def _generate_database_node(
        self,
        node: CompileRequest.Node,
        implementation_str: str,
        requested_inputs: dict[int, data_types.LeqoSupportedType],
        width: int,
        depth: int | None,
    ) -> models.BaseNode | None:
        if not isinstance(node, CompileRequest.EncodeValueNode):
            return None
        self._check_constraints(node, requested_inputs)

        requested_input = requested_inputs[0]
        if isinstance(requested_input, (data_types.ArrayType, ast.ArrayType)):
            return None

        converted_input_type = self._convert_to_input_type(requested_input)

        new_node = models.EncodeValueNode(
            type=models.NodeType(node.type),
            depth=depth,
            width=width,
            implementation=implementation_str,
            encoding=models.EncodingType(node.encoding),
            bounds=node.bounds,
        )
        input_node = models.Input(
            index=0,
            type=converted_input_type,
            size=requested_input.size,
        )
        new_node.inputs.append(input_node)

        return new_node

    @override
    async def _enrich_impl(
        self, node: CompileRequest.Node, constraints: Constraints | None
    ) -> list[EnrichmentResult]:
        if isinstance(node, CompileRequest.EncodeValueNode) and node.encoding in {
            "basis",
            "angle",
        }:
            db_results = await super()._enrich_impl(node, constraints)
            if db_results:
                return db_results

            if constraints is None:
                raise InputCountMismatch(node, actual=0, should_be="equal", expected=1)

            self._check_constraints(node, constraints.requested_inputs)

            classical_input = cast(
                data_types.LeqoSupportedClassicalType, constraints.requested_inputs[0]
            )
            if node.encoding == "basis":
                return [
                    self._generate_basis_enrichment(
                        node,
                        classical_input,
                        constraints.requested_input_values.get(0),
                    ),
                ]
            return [
                self._generate_angle_enrichment(
                    node,
                    classical_input,
                    constraints.requested_input_values.get(0),
                ),
            ]

        return await super()._enrich_impl(node, constraints)

    @override
    def _generate_query(
        self, node: CompileRequest.Node, constraints: Constraints | None
    ) -> Select[tuple[models.BaseNode]] | None:
        if not isinstance(node, CompileRequest.EncodeValueNode):
            return None

        if constraints is None:
            raise InputCountMismatch(
                node,
                actual=0,
                should_be="equal",
                expected=1,
            )

        self._check_constraints(node, constraints.requested_inputs)

        requested_input = constraints.requested_inputs[0]
        if isinstance(requested_input, (data_types.ArrayType, ast.ArrayType)):
            return None

        converted_input_type = self._convert_to_input_type(requested_input)

        where_clauses: list[Any] = [
            models.EncodeValueNode.type == models.NodeType(node.type),
            models.EncodeValueNode.encoding == models.EncodingType(node.encoding),
            models.EncodeValueNode.bounds == node.bounds,
            models.Input.index == 0,
            models.Input.type == converted_input_type,
        ]
        if hasattr(requested_input, "size") and requested_input.size is not None:
            where_clauses.append(models.Input.size >= requested_input.size)

        return cast(
            Select[tuple[models.BaseNode]],
            select(models.EncodeValueNode)
            .join(models.Input, models.EncodeValueNode.inputs)
            .where(*where_clauses),
        )

    def _get_array_length(self, array_type: Any) -> int:
        val = 0
        if isinstance(array_type, data_types.ArrayType):
            val = array_type.length
        elif isinstance(array_type, ast.ArrayType):
            val = array_type.dimensions[0]

        if isinstance(val, list) and val:
            val = val[0]

        if hasattr(val, "value"):
            val = val.value

        return int(val)

    def _get_element_type(self, array_type: Any) -> Any:
        if isinstance(array_type, data_types.ArrayType):
            return array_type.element_type
        if isinstance(array_type, ast.ArrayType):
            return array_type.base_type
        return None

    def _generate_basis_enrichment(
        self,
        node: CompileRequest.EncodeValueNode,
        classical_input: data_types.LeqoSupportedClassicalType,
        input_value: Any | None,
    ) -> EnrichmentResult:
        size = self._determine_register_size(node, classical_input)
        constant_indices: list[int] | None = None
        if input_value is not None:
            try:
                constant_indices = self._constant_basis_indices(
                    classical_input, size, input_value
                )
            except RuntimeError:
                constant_indices = None

        signed_output = self._basis_output_requires_signed_flag(
            classical_input, input_value
        )
        statements = self._build_basis_statements(
            classical_input, size, constant_indices, signed_output
        )
        depth = size if constant_indices is None else len(constant_indices)
        return EnrichmentResult(
            implementation(node, statements),
            ImplementationMetaData(width=size, depth=depth),
        )

    def _generate_angle_enrichment(
        self,
        node: CompileRequest.EncodeValueNode,
        classical_input: data_types.LeqoSupportedClassicalType,
        input_value: Any | None,
    ) -> EnrichmentResult:
        if isinstance(classical_input, (data_types.ArrayType, ast.ArrayType)):
            register_size = self._get_array_length(classical_input)
        else:
            register_size = self._determine_register_size(node, classical_input)

        rotation_map: dict[int, float] | None = None
        if input_value is not None:
            try:
                rotation_map = self._constant_angle_rotations(
                    classical_input, register_size, input_value
                )
            except RuntimeError:
                rotation_map = None

        statements = self._build_angle_statements(
            classical_input,
            register_size,
            rotation_map,
        )
        depth = (
            sum(1 for angle in rotation_map.values() if angle != 0)
            if rotation_map is not None
            else register_size
        )
        return EnrichmentResult(
            implementation(node, statements),
            ImplementationMetaData(width=register_size, depth=depth),
        )

    def _determine_register_size(
        self,
        node: CompileRequest.EncodeValueNode,
        classical_input: data_types.LeqoSupportedClassicalType,
    ) -> int:
        """Determines size while satisfying PLR0911."""
        res: int
        if node.encoding == "angle" and not isinstance(
            classical_input, (data_types.ArrayType, ast.ArrayType)
        ):
            res = 1
        elif isinstance(classical_input, ast.ArrayType):
            res = self._get_array_length(classical_input)
        elif isinstance(classical_input, ast.FloatType):
            res = 1
        else:
            size = 0
            match classical_input:
                case (
                    data_types.BoolType()
                    | data_types.IntType()
                    | data_types.ArrayType()
                ):
                    size = classical_input.size
                case data_types.BitType():
                    size = classical_input.size or 1
                case data_types.FloatType():
                    size = 1
                case _:
                    if hasattr(classical_input, "size") and isinstance(
                        classical_input.size, int
                    ):
                        size = classical_input.size
                    else:
                        raise InputTypeMismatch(
                            node, 0, actual=classical_input, expected="classical type"
                        )
            if size <= 0:
                raise InputSizeMismatch(node, 0, actual=size, expected=1)
            res = size
        return res

    def _constant_basis_indices(
        self,
        classical_input: data_types.LeqoSupportedClassicalType,
        register_size: int,
        raw_value: Any,
    ) -> list[int]:
        if isinstance(classical_input, data_types.FloatType):
            raise RuntimeError("FloatType not supported for basis encoding")

        if isinstance(classical_input, (data_types.ArrayType, ast.ArrayType)):
            values = self._coerce_array_constant_value(classical_input, raw_value)
            element_type = self._get_element_type(classical_input)

            if isinstance(element_type, (data_types.FloatType, ast.FloatType)):
                raise RuntimeError("Float Array not supported for basis encoding")

            if hasattr(element_type, "size"):
                element_size = element_type.size
            elif isinstance(element_type, ast.ArrayType) or hasattr(
                element_type, "value"
            ):
                element_size = element_type.value
            else:
                element_size = 32

            if hasattr(element_size, "value"):
                element_size = element_size.value
            element_size = int(element_size)

            mask_limit = (1 << element_size) - 1
            indices: list[int] = []
            for element_index, element_value in enumerate(values):
                mask = int(element_value) & mask_limit
                base_offset = element_index * element_size
                indices.extend(
                    base_offset + bit
                    for bit in range(element_size)
                    if (mask >> bit) & 1
                )
            return indices

        try:
            value = int(raw_value)
        except (TypeError, ValueError) as exc:
            msg = "Unsupported classical input for basis encoding"
            raise RuntimeError(msg) from exc

        mask = value & ((1 << register_size) - 1)
        return [index for index in range(register_size) if (mask >> index) & 1]

    def _basis_output_requires_signed_flag(
        self,
        classical_input: data_types.LeqoSupportedClassicalType,
        raw_value: Any | None,
    ) -> bool:
        if raw_value is None:
            return False

        if isinstance(classical_input, data_types.IntType):
            try:
                return int(raw_value) < 0
            except (TypeError, ValueError):
                return False

        if isinstance(classical_input, (data_types.ArrayType, ast.ArrayType)):
            try:
                values = self._coerce_array_constant_value(classical_input, raw_value)
                return any(value < 0 for value in values)
            except RuntimeError:
                return False

        return False

    @staticmethod
    def _coerce_array_constant_value(
        array_type: data_types.ArrayType | ast.ArrayType,
        raw_value: Any,
    ) -> list[float | int]:
        val_to_check = raw_value.values if hasattr(raw_value, "values") else raw_value
        data_is_float = False

        if (
            isinstance(val_to_check, (list, Iterable))
            and not isinstance(val_to_check, (str, bytes))
            and val_to_check
        ):
            sample = val_to_check[0]
            sample_val = sample.value if hasattr(sample, "value") else sample
            if isinstance(sample_val, float) or (
                isinstance(sample_val, str) and "." in str(sample_val)
            ):
                data_is_float = True

        # 2. Check declared type
        if isinstance(array_type, data_types.ArrayType):
            type_is_float = isinstance(array_type.element_type, data_types.FloatType)
            len_obj = (
                array_type.length[0]
                if isinstance(array_type.length, list) and array_type.length
                else array_type.length
            )
            expected_length = int(
                len_obj.value if hasattr(len_obj, "value") else len_obj
            )
        elif isinstance(array_type, ast.ArrayType):
            type_is_float = isinstance(array_type.base_type, ast.FloatType)
            dim = array_type.dimensions[0]
            expected_length = dim.value if hasattr(dim, "value") else int(dim)
        else:
            raise RuntimeError("Unknown array type structure")

        # 3. Choose converter (Float wins if data says so)
        converter = float if (type_is_float or data_is_float) else int

        # 4. Convert
        actual_raw = raw_value.values if hasattr(raw_value, "values") else raw_value

        if isinstance(actual_raw, str):
            parts = [
                p.strip() for p in actual_raw.replace(";", ",").split(",") if p.strip()
            ]
            values = [converter(p) for p in parts]
        elif isinstance(actual_raw, Iterable) and not isinstance(
            actual_raw, (bytes, bytearray)
        ):
            values = [
                converter(v.value if hasattr(v, "value") else v) for v in actual_raw
            ]
        elif actual_raw is None:
            raise RuntimeError("Unsupported classical input")
        else:
            values = [
                converter(
                    actual_raw.value if hasattr(actual_raw, "value") else actual_raw
                )
            ]

        if len(values) != expected_length:
            msg = (
                f"Array length mismatch: expected {expected_length}, got {len(values)}"
            )
            raise RuntimeError(msg)
        return values

    def _constant_angle_rotations(
        self,
        classical_input: data_types.LeqoSupportedClassicalType,
        _register_size: int,
        raw_value: Any,
    ) -> dict[int, float]:
        """Calculates rotations while satisfying PLR0911."""
        final_rotations: dict[int, float]

        if isinstance(classical_input, (data_types.FloatType, ast.FloatType)):
            try:
                v = raw_value.value if hasattr(raw_value, "value") else raw_value
                final_rotations = {0: max(0.0, min(float(v), 2 * pi))}
            except (TypeError, ValueError) as exc:
                raise RuntimeError("Unsupported input for angle encoding") from exc

        elif isinstance(classical_input, (data_types.ArrayType, ast.ArrayType)):
            values = self._coerce_array_constant_value(classical_input, raw_value)
            float_vals = [float(v) for v in values]
            if not float_vals:
                length = self._get_array_length(classical_input)
                final_rotations = dict.fromkeys(range(length), 0.0)
            else:
                norm = sqrt(sum(v**2 for v in float_vals))
                if norm > 0:
                    final_rotations = {
                        index: (v / norm)
                        for index, v in enumerate(float_vals)
                    }
                else:
                    final_rotations = {index: 0.0 for index in range(len(float_vals))}

        elif isinstance(classical_input, data_types.IntType):
            v = int(raw_value.value if hasattr(raw_value, "value") else raw_value)
            bit_size = classical_input.size or 32
            max_val = (1 << bit_size) - 1
            normalized = (v / max_val) * (pi / 2) if max_val > 0 else 0.0
            final_rotations = {0: normalized}

        elif isinstance(classical_input, (data_types.BitType, data_types.BoolType)):
            v = int(raw_value.value if hasattr(raw_value, "value") else raw_value)
            final_rotations = {0: v * (pi / 2)}
        else:
            final_rotations = {0: 0.0}

        return final_rotations

    def _build_basis_statements(
        self,
        classical_input: data_types.LeqoSupportedClassicalType,
        register_size: int,
        constant_indices: list[int] | None,
        signed_output: bool,
    ) -> list[ast.Statement]:
        qubit_identifier = ast.Identifier("encoded")
        statements: list[ast.Statement] = [ast.Include("stdgates.inc")]

        if constant_indices is None:
            value_identifier = ast.Identifier("value")
            ast_type = (
                classical_input.to_ast()
                if hasattr(classical_input, "to_ast")
                else classical_input
            )
            classical_decl = ast.ClassicalDeclaration(ast_type, value_identifier, None)
            classical_decl.annotations = [ast.Annotation("leqo.input", "0")]
            statements.append(classical_decl)
        else:
            value_identifier = None

        qubit_decl = ast.QubitDeclaration(
            qubit_identifier, ast.IntegerLiteral(register_size)
        )
        statements.append(qubit_decl)

        if constant_indices is None:
            assert value_identifier is not None
            for index in range(register_size):
                condition = self._bit_condition_expression(
                    classical_input, value_identifier, index
                )
                target = ast.IndexedIdentifier(
                    qubit_identifier, [[ast.IntegerLiteral(index)]]
                )
                gate = ast.QuantumGate(
                    modifiers=[],
                    name=ast.Identifier("x"),
                    arguments=[],
                    qubits=[target],
                    duration=None,
                )
                statements.append(ast.BranchingStatement(condition, [gate], []))
        else:
            for index in constant_indices:
                target = ast.IndexedIdentifier(
                    qubit_identifier, [[ast.IntegerLiteral(index)]]
                )
                gate = ast.QuantumGate(
                    modifiers=[],
                    name=ast.Identifier("x"),
                    arguments=[],
                    qubits=[target],
                    duration=None,
                )
                statements.append(gate)

        output_alias = leqo_output("out", 0, qubit_identifier)
        if signed_output:
            output_alias.annotations.append(
                ast.Annotation("leqo.twos_complement", "true")
            )
        statements.append(output_alias)
        return statements

    def _build_angle_statements(
        self,
        classical_input: data_types.LeqoSupportedClassicalType,
        register_size: int,
        rotation_map: dict[int, float] | None,
    ) -> list[ast.Statement]:
        qubit_identifier = ast.Identifier("encoded")

        statements: list[ast.Statement] = [ast.Include("stdgates.inc")]
        value_identifier: ast.Identifier | None = None
        if rotation_map is None:
            value_identifier = ast.Identifier("value")
            ast_type = (
                classical_input.to_ast()
                if hasattr(classical_input, "to_ast")
                else classical_input
            )
            classical_decl = ast.ClassicalDeclaration(ast_type, value_identifier, None)
            classical_decl.annotations = [ast.Annotation("leqo.input", "0")]
            statements.append(classical_decl)

        statements.append(
            ast.QubitDeclaration(qubit_identifier, ast.IntegerLiteral(register_size))
        )

        context = _AngleEmissionContext(
            statements=statements,
            qubit_identifier=qubit_identifier,
            register_size=register_size,
            rotation_map=rotation_map,
            value_identifier=value_identifier,
        )
        self._emit_angle_statements(classical_input, context)

        statements.append(leqo_output("out", 0, qubit_identifier))
        return statements

    def _emit_angle_statements(
        self,
        classical_input: data_types.LeqoSupportedClassicalType,
        context: _AngleEmissionContext,
    ) -> None:
        if isinstance(classical_input, (data_types.FloatType, ast.FloatType)):
            self._emit_float_angle_statements(context)
        elif isinstance(classical_input, (data_types.ArrayType, ast.ArrayType)):
            self._emit_array_angle_statements(context)
        else:
            self._emit_generic_angle_statements(classical_input, context)

    def _emit_float_angle_statements(self, context: _AngleEmissionContext) -> None:
        rotation_map = context.rotation_map
        statements = context.statements
        qubit_identifier = context.qubit_identifier

        if rotation_map is None:
            value_identifier = context.value_identifier
            assert value_identifier is not None
            rotation_argument = ast.BinaryExpression(
                ast.BinaryOperator["*"],
                ast.FloatLiteral(2.0),
                value_identifier,
            )
            statements.append(
                ast.QuantumGate(
                    modifiers=[],
                    name=ast.Identifier("ry"),
                    arguments=[rotation_argument],
                    qubits=[qubit_identifier],
                    duration=None,
                )
            )
            return

        angle = rotation_map.get(0)
        if angle:
            statements.append(
                ast.QuantumGate(
                    modifiers=[],
                    name=ast.Identifier("ry"),
                    arguments=[ast.FloatLiteral(2 * angle)],
                    qubits=[qubit_identifier],
                    duration=None,
                )
            )

    def _emit_array_angle_statements(self, context: _AngleEmissionContext) -> None:
        statements = context.statements
        rotation_map = context.rotation_map
        qubit_identifier = context.qubit_identifier
        register_size = context.register_size

        if rotation_map is None:
            value_identifier = context.value_identifier
            assert value_identifier is not None
            multiplier = ast.FloatLiteral(2.0)
            for index in range(register_size):
                target = ast.IndexedIdentifier(
                    qubit_identifier, [[ast.IntegerLiteral(index)]]
                )
                value_expr = ast.IndexExpression(
                    collection=value_identifier,
                    index=[ast.IntegerLiteral(index)],
                )
                rotation_expr = ast.BinaryExpression(
                    ast.BinaryOperator["*"],
                    multiplier,
                    value_expr,
                )
                statements.append(
                    ast.QuantumGate(
                        modifiers=[],
                        name=ast.Identifier("ry"),
                        arguments=[rotation_expr],
                        qubits=[target],
                        duration=None,
                    )
                )
            return

        for index in range(register_size):
            angle = rotation_map.get(index)
            if angle is not None and angle != 0.0:
                rotation_value = 2 * angle
                target = ast.IndexedIdentifier(
                    qubit_identifier, [[ast.IntegerLiteral(index)]]
                )
                statements.append(
                    ast.QuantumGate(
                        modifiers=[],
                        name=ast.Identifier("ry"),
                        arguments=[ast.FloatLiteral(rotation_value)],
                        qubits=[target],
                        duration=None,
                    )
                )

    def _emit_generic_angle_statements(
        self,
        classical_input: data_types.LeqoSupportedClassicalType,
        context: _AngleEmissionContext,
    ) -> None:
        statements = context.statements
        qubit_identifier = context.qubit_identifier
        register_size = context.register_size
        rotation_map = context.rotation_map

        if rotation_map is None:
            value_identifier = context.value_identifier
            assert value_identifier is not None
            for index in range(register_size):
                condition = self._bit_condition_expression(
                    classical_input, value_identifier, index
                )
                target = ast.IndexedIdentifier(
                    qubit_identifier, [[ast.IntegerLiteral(index)]]
                )
                rotation_gate = ast.QuantumGate(
                    modifiers=[],
                    name=ast.Identifier("ry"),
                    arguments=[ast.FloatLiteral(pi)],
                    qubits=[target],
                    duration=None,
                )
                statements.append(
                    ast.BranchingStatement(condition, [rotation_gate], [])
                )
            return

        for index in sorted(rotation_map):
            angle = rotation_map[index]
            if angle is not None and angle != 0.0:
                rotation_value = 2 * angle
                target = ast.IndexedIdentifier(
                    qubit_identifier, [[ast.IntegerLiteral(index)]]
                )
                statements.append(
                    ast.QuantumGate(
                        modifiers=[],
                        name=ast.Identifier("ry"),
                        arguments=[ast.FloatLiteral(rotation_value)],
                        qubits=[target],
                        duration=None,
                    )
                )

    def _bit_condition_expression(
        self,
        classical_input: data_types.LeqoSupportedClassicalType,
        value_identifier: ast.Identifier,
        index: int,
    ) -> ast.BinaryExpression | ast.Identifier:
        if isinstance(classical_input, (data_types.ArrayType, ast.ArrayType)):
            element_type = self._get_element_type(classical_input)
            if hasattr(element_type, "size"):
                element_size = element_type.size
            elif isinstance(element_type, ast.ArrayType) or hasattr(
                element_type, "value"
            ):
                element_size = element_type.value
            else:
                element_size = 32

            if hasattr(element_size, "value"):
                element_size = element_size.value
            element_size = int(element_size)

            element_index = index // element_size
            bit_index = index % element_size

            element_expr = ast.IndexExpression(
                collection=value_identifier,
                index=[ast.IntegerLiteral(element_index)],
            )
            shifted = ast.BinaryExpression(
                ast.BinaryOperator[">>"],
                element_expr,
                ast.IntegerLiteral(bit_index),
            )
            masked = ast.BinaryExpression(
                ast.BinaryOperator["&"],
                shifted,
                ast.IntegerLiteral(1),
            )
            return ast.BinaryExpression(
                ast.BinaryOperator["=="],
                masked,
                ast.IntegerLiteral(1),
            )

        match classical_input:
            case data_types.BoolType():
                return value_identifier
            case data_types.BitType(size=None):
                return value_identifier
            case data_types.BitType():
                element = ast.IndexExpression(
                    collection=value_identifier,
                    index=[ast.IntegerLiteral(index)],
                )
                return ast.BinaryExpression(
                    ast.BinaryOperator["=="],
                    element,
                    ast.IntegerLiteral(1),
                )
            case data_types.IntType():
                shifted = ast.BinaryExpression(
                    ast.BinaryOperator[">>"],
                    value_identifier,
                    ast.IntegerLiteral(index),
                )
                masked = ast.BinaryExpression(
                    ast.BinaryOperator["&"],
                    shifted,
                    ast.IntegerLiteral(1),
                )
                return ast.BinaryExpression(
                    ast.BinaryOperator["=="],
                    masked,
                    ast.IntegerLiteral(1),
                )
            case data_types.FloatType():
                raise RuntimeError("FloatType not supported for basis encoding")
            case _:
                raise RuntimeError("Unsupported classical input for basis encoding")

"""
Provides enricher strategy for enriching :class:`~app.model.CompileRequest.EncodeValueNode` from a database.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from math import isqrt, log2, pi
from typing import Any, cast, override

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
    IndexExpression,
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
from app.enricher.models import (
    BaseNode,
    EncodingType,
    Input,
    InputType,
    NodeType,
)
from app.enricher.models import (
    EncodeValueNode as EncodeNodeTable,
)
from app.enricher.utils import implementation, leqo_output
from app.model.CompileRequest import EncodeValueNode
from app.model.CompileRequest import Node as FrontendNode
from app.model.data_types import (
    ArrayType,
    BitType,
    BoolType,
    FloatType,
    IntType,
    LeqoSupportedClassicalType,
    LeqoSupportedType,
    QubitType,
)
from app.model.exceptions import (
    InputCountMismatch,
    InputSizeMismatch,
    InputTypeMismatch,
)


@dataclass
class _AngleEmissionContext:
    statements: list[Statement]
    qubit_identifier: Identifier
    register_size: int
    rotation_map: dict[int, float] | None
    value_identifier: Identifier | None
    bounds: int


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
            case ArrayType():
                msg = "Unsupported input type: array"
                raise RuntimeError(msg)
            case _:
                raise RuntimeError(f"Unsupported input type: {node_type}")

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

        if node.encoding in {"amplitude", "matrix"} and not isinstance(
            requested_inputs[0], ArrayType
        ):
            raise InputTypeMismatch(
                node,
                input_index=0,
                actual=requested_inputs[0],
                expected="array",
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

        requested_input = requested_inputs[0]
        if isinstance(requested_input, ArrayType):
            return None

        converted_input_type = self._convert_to_input_type(requested_input)

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
            size=requested_input.size,
        )
        new_node.inputs.append(input_node)

        return new_node

    @override
    async def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> list[EnrichmentResult]:
        if isinstance(node, EncodeValueNode) and node.encoding in {
            "basis",
            "angle",
            "amplitude",
            "matrix",
        }:
            # Prefer database-backed implementations first to keep behaviour consistent
            # with other encoders and reuse vetted circuits when available.
            db_results = await super()._enrich_impl(node, constraints)
            if db_results:
                return db_results

            if constraints is None:
                raise InputCountMismatch(node, actual=0, should_be="equal", expected=1)

            self._check_constraints(node, constraints.requested_inputs)

            # On cache miss, synthesise the basis encoding implementation on the fly.
            classical_input = cast(
                LeqoSupportedClassicalType, constraints.requested_inputs[0]
            )
            if node.encoding == "basis":
                return [
                    self._generate_basis_enrichment(
                        node,
                        classical_input,
                        constraints.requested_input_values.get(0),
                    ),
                ]

            if node.encoding == "angle":
                return [
                    self._generate_angle_enrichment(
                        node,
                        classical_input,
                        constraints.requested_input_values.get(0),
                    ),
                ]

            if node.encoding == "matrix":
                return [
                    self.generate_matrix_enrichment(
                        node,
                        classical_input,
                        constraints.requested_input_values.get(0),
                    ),
                ]

            # amplitude
            return [
                self.generate_amplitude_enrichment(
                    node,
                    classical_input,
                    constraints.requested_input_values.get(0),
                ),
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

        requested_input = constraints.requested_inputs[0]
        if isinstance(requested_input, ArrayType):
            return None

        converted_input_type = self._convert_to_input_type(requested_input)

        where_clauses: list[Any] = [
            EncodeNodeTable.type == NodeType(node.type),
            EncodeNodeTable.encoding == EncodingType(node.encoding),
            EncodeNodeTable.bounds == node.bounds,
            Input.index == 0,
            Input.type == converted_input_type,
        ]
        if requested_input.size is not None:
            where_clauses.append(Input.size >= requested_input.size)

        return cast(
            Select[tuple[BaseNode]],
            select(EncodeNodeTable)
            .join(Input, EncodeNodeTable.inputs)
            .where(*where_clauses),
        )

    def _generate_basis_enrichment(
        self,
        node: EncodeValueNode,
        classical_input: LeqoSupportedClassicalType,
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
        node: EncodeValueNode,
        classical_input: LeqoSupportedClassicalType,
        input_value: Any | None,
    ) -> EnrichmentResult:
        register_size = (
            classical_input.length
            if isinstance(classical_input, ArrayType)
            else self._determine_register_size(node, classical_input)
        )
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
            node.bounds,
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

    def _coerce_amplitude_array_value(
        self,
        array_type: ArrayType,
        raw_value: Any,
    ) -> list[float]:
        """the raw input value to a list of floats for amplitude encoding."""
        if isinstance(raw_value, str):
            parts = [
                part.strip()
                for part in raw_value.replace(";", ",").split(",")
                if part.strip() != ""
            ]
            values = [float(part) for part in parts]
        elif isinstance(raw_value, Iterable) and not isinstance(
            raw_value, (bytes, bytearray)
        ):
            values = [float(value) for value in raw_value]
        elif raw_value is None:
            raise RuntimeError("Unsupported input for amplitude encoding")
        else:
            values = [float(raw_value)]

        if len(values) != array_type.length:
            raise RuntimeError("Input length does not match array length")

        return values

    def generate_amplitude_enrichment(
        self,
        node: EncodeValueNode,
        classical_input: LeqoSupportedClassicalType,
        input_value: Any | None,
    ) -> EnrichmentResult:
        if not isinstance(classical_input, ArrayType):
            raise InputTypeMismatch(node, 0, actual=classical_input, expected="array")

        if input_value is None:
            raise EncodingNotSupported(node)

        values = self._coerce_amplitude_array_value(classical_input, input_value)

        try:
            import numpy as np
            import openqasm3
            from qiskit import qasm3
            from qiskit.circuit import QuantumCircuit, QuantumRegister
            from qiskit.circuit.library import StatePreparation
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Amplitude encoding needs numpy, qiskit and openqasm3 "
                "install with `uv add numpy qiskit openqasm3`."
            ) from exc

        vec = np.asarray(values, dtype=float)

        if node.bounds == 1:
            if np.any(vec < 0.0) or np.any(vec > 1.0):
                raise RuntimeError(
                    "Amplitude encoding with bounds=1 expects all values in [0, 1]."
                )

        if vec.size < 2:
            raise RuntimeError(
                "Amplitude encoding needs an array with at least 2 values."
            )

        # Pad to nearest power of 2 #next test
        target_len = 1 << (int(vec.size) - 1).bit_length()
        if target_len != vec.size:
            vec = np.pad(vec, (0, target_len - vec.size), mode="constant")

        # Check norm and normalize
        norm = np.linalg.norm(vec)
        if norm == 0:
            raise RuntimeError("Amplitude encoding input vector has norm 0.")

        # Always normalize to valid quantum state important: amplitudes must have norm 1
        vec = vec / norm

        n_qubits = int(log2(int(vec.size)))

        qreg = QuantumRegister(n_qubits, "encoded")
        qc = QuantumCircuit(qreg, name="amplitude_encoding")

        qc.append(StatePreparation(vec.astype(complex)), qreg)

        # Decompose a few times so QASM export is easier.
        for _ in range(4):
            qc = qc.decompose()

        qasm_text = qasm3.dumps(qc)
        prog = openqasm3.parse(qasm_text)
        statements = list(prog.statements)

        if not any(isinstance(st, Include) for st in statements):
            statements.insert(0, Include("stdgates.inc"))

        statements.append(leqo_output("out", 0, Identifier("encoded")))

        return EnrichmentResult(
            implementation(node, statements),
            ImplementationMetaData(
                width=n_qubits,
                depth=qc.depth(),
            ),
        )

    def _coerce_matrix_array_value(
        self,
        array_type: ArrayType,
        raw_value: Any,
    ) -> list[float]:
        """Convert the raw input value to a flat list of floats for matrix encoding."""
        actual_raw = raw_value.values if hasattr(raw_value, "values") else raw_value

        if isinstance(actual_raw, str):
            parts = [
                part.strip()
                for part in actual_raw.replace(";", ",").split(",")
                if part.strip() != ""
            ]
            values = [float(part) for part in parts]
        elif isinstance(actual_raw, Iterable) and not isinstance(
            actual_raw, (bytes, bytearray, str)
        ):
            values = [
                float(value.value if hasattr(value, "value") else value)
                for value in actual_raw
            ]
        elif actual_raw is None:
            raise RuntimeError(
                "Matrix encoding currently requires a constant array input."
            )
        else:
            values = [
                float(actual_raw.value if hasattr(actual_raw, "value") else actual_raw)
            ]

        if len(values) != array_type.length:
            raise RuntimeError("Input length does not match array length.")

        return values

    def _reshape_and_validate_unitary_matrix(
        self,
        flat_values: list[float],
    ) -> tuple[Any, int]:
        """Reshape a flat array into a square matrix and validate the v1 constraints."""
        import numpy as np

        total_len = len(flat_values)
        dim = isqrt(total_len)

        if dim * dim != total_len:
            raise RuntimeError(
                "Matrix encoding expects a flat square matrix (length must be n^2)."
            )

        if dim < 2:
            raise RuntimeError("Matrix encoding needs at least a 2x2 matrix.")

        if dim & (dim - 1) != 0:
            raise RuntimeError("Matrix encoding expects a 2^n x 2^n matrix.")

        matrix = np.asarray(flat_values, dtype=complex).reshape((dim, dim))
        identity = np.eye(dim, dtype=complex)

        if not np.allclose(matrix.conj().T @ matrix, identity, atol=1e-8):
            raise RuntimeError("Matrix encoding v1 expects a unitary matrix.")

        return matrix, int(log2(dim))

    def generate_matrix_enrichment(
        self,
        node: EncodeValueNode,
        classical_input: LeqoSupportedClassicalType,
        input_value: Any | None,
    ) -> EnrichmentResult:
        if not isinstance(classical_input, ArrayType):
            raise InputTypeMismatch(node, 0, actual=classical_input, expected="array")

        if input_value is None:
            raise RuntimeError(
                "Matrix encoding currently requires a constant array input."
            )

        flat_values = self._coerce_matrix_array_value(classical_input, input_value)
        matrix, n_qubits = self._reshape_and_validate_unitary_matrix(flat_values)

        try:
            import openqasm3
            from qiskit import qasm3
            from qiskit.circuit import QuantumCircuit, QuantumRegister
            from qiskit.circuit.library import UnitaryGate
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Matrix encoding needs numpy, qiskit and openqasm3 "
                "install with `uv add numpy qiskit openqasm3`."
            ) from exc

        qreg = QuantumRegister(n_qubits, "encoded")
        qc = QuantumCircuit(qreg, name="matrix_encoding")

        qc.append(UnitaryGate(matrix), qreg)

        for _ in range(4):
            qc = qc.decompose()

        qasm_text = qasm3.dumps(qc)
        prog = openqasm3.parse(qasm_text)
        statements = list(prog.statements)

        if not any(isinstance(st, Include) for st in statements):
            statements.insert(0, Include("stdgates.inc"))

        statements.append(leqo_output("out", 0, Identifier("encoded")))

        return EnrichmentResult(
            implementation(node, statements),
            ImplementationMetaData(
                width=n_qubits,
                depth=qc.depth(),
            ),
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
            case ArrayType():
                size = classical_input.size
            case _:
                raise InputTypeMismatch(
                    node,
                    0,
                    actual=classical_input,
                    expected="bit, int, bool, float or array",
                )

        if size <= 0:
            raise InputSizeMismatch(node, 0, actual=size, expected=1)

        return size

    def _constant_basis_indices(
        self,
        classical_input: LeqoSupportedClassicalType,
        register_size: int,
        raw_value: Any,
    ) -> list[int]:
        if isinstance(classical_input, FloatType):
            raise RuntimeError("FloatType not supported for basis encoding")

        if isinstance(classical_input, ArrayType):
            values = self._coerce_array_constant_value(classical_input, raw_value)
            element_size = classical_input.element_type.size
            mask_limit = (1 << element_size) - 1
            indices: list[int] = []
            for element_index, element_value in enumerate(values):
                mask = element_value & mask_limit
                base_offset = element_index * element_size
                indices.extend(
                    base_offset + bit
                    for bit in range(element_size)
                    if (mask >> bit) & 1
                )
            return indices

        try:
            value = int(raw_value)
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            msg = "Unsupported classical input for basis encoding"
            raise RuntimeError(msg) from exc

        mask = value & ((1 << register_size) - 1)
        return [index for index in range(register_size) if (mask >> index) & 1]

    def _basis_output_requires_signed_flag(
        self,
        classical_input: LeqoSupportedClassicalType,
        raw_value: Any | None,
    ) -> bool:
        if raw_value is None:
            return False

        if isinstance(classical_input, IntType):
            try:
                return int(raw_value) < 0
            except (TypeError, ValueError):
                return False

        if isinstance(classical_input, ArrayType):
            try:
                values = self._coerce_array_constant_value(classical_input, raw_value)
            except RuntimeError:
                return False
            return any(value < 0 for value in values)

        return False

    @staticmethod
    def _coerce_array_constant_value(
        array_type: ArrayType,
        raw_value: Any,
    ) -> list[int]:
        if isinstance(raw_value, str):
            parts = [
                part.strip()
                for part in raw_value.replace(";", ",").split(",")
                if part.strip() != ""
            ]
            values = [int(part) for part in parts]
        elif isinstance(raw_value, Iterable) and not isinstance(
            raw_value, (bytes, bytearray)
        ):
            values = [int(value) for value in raw_value]
        elif raw_value is None:
            msg = "Unsupported classical input for basis encoding"
            raise RuntimeError(msg)
        else:
            values = [int(raw_value)]

        if len(values) != array_type.length:
            msg = "Unsupported classical input for basis encoding"
            raise RuntimeError(msg)

        return values

    def _constant_angle_rotations(
        self,
        classical_input: LeqoSupportedClassicalType,
        register_size: int,
        raw_value: Any,
    ) -> dict[int, float]:
        if isinstance(classical_input, FloatType):
            try:
                angle = float(raw_value)
            except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
                msg = "Unsupported classical input for angle encoding"
                raise RuntimeError(msg) from exc
            clamped = max(0.0, min(angle, 2 * pi))
            return {0: clamped}

        if isinstance(classical_input, ArrayType):
            values = self._coerce_array_constant_value(classical_input, raw_value)
            mask_limit = (1 << classical_input.element_type.size) - 1
            if mask_limit <= 0:
                return dict.fromkeys(range(classical_input.length), 0.0)
            return {
                index: float(value & mask_limit) for index, value in enumerate(values)
            }

        indices = self._constant_basis_indices(
            classical_input,
            register_size,
            raw_value,
        )
        return dict.fromkeys(indices, pi)

    def _build_basis_statements(
        self,
        classical_input: LeqoSupportedClassicalType,
        register_size: int,
        constant_indices: list[int] | None,
        signed_output: bool,
    ) -> list[Statement]:
        qubit_identifier = Identifier("encoded")

        statements: list[Statement] = [Include("stdgates.inc")]

        if constant_indices is None:
            value_identifier = Identifier("value")
            classical_decl = ClassicalDeclaration(
                classical_input.to_ast(), value_identifier, None
            )
            classical_decl.annotations = [Annotation("leqo.input", "0")]
            statements.append(classical_decl)
        else:
            value_identifier = None

        qubit_decl = QubitDeclaration(qubit_identifier, IntegerLiteral(register_size))
        statements.append(qubit_decl)

        if constant_indices is None:
            assert value_identifier is not None
            for index in range(register_size):
                condition = self._bit_condition_expression(
                    classical_input, value_identifier, index
                )
                target = IndexedIdentifier(qubit_identifier, [[IntegerLiteral(index)]])
                gate = QuantumGate(
                    modifiers=[],
                    name=Identifier("x"),
                    arguments=[],
                    qubits=[target],
                    duration=None,
                )
                statements.append(BranchingStatement(condition, [gate], []))
        else:
            for index in constant_indices:
                target = IndexedIdentifier(qubit_identifier, [[IntegerLiteral(index)]])
                gate = QuantumGate(
                    modifiers=[],
                    name=Identifier("x"),
                    arguments=[],
                    qubits=[target],
                    duration=None,
                )
                statements.append(gate)

        # Expose the encoded register as the sole output of the node.
        output_alias = leqo_output("out", 0, qubit_identifier)
        if signed_output:
            output_alias.annotations.append(Annotation("leqo.twos_complement", "true"))
        statements.append(output_alias)
        return statements

    def _build_angle_statements(
        self,
        classical_input: LeqoSupportedClassicalType,
        register_size: int,
        rotation_map: dict[int, float] | None,
        bounds: int,
    ) -> list[Statement]:
        qubit_identifier = Identifier("encoded")

        statements: list[Statement] = [Include("stdgates.inc")]
        value_identifier: Identifier | None = None
        if rotation_map is None:
            value_identifier = Identifier("value")
            classical_decl = ClassicalDeclaration(
                classical_input.to_ast(), value_identifier, None
            )
            classical_decl.annotations = [Annotation("leqo.input", "0")]
            statements.append(classical_decl)

        statements.append(
            QubitDeclaration(qubit_identifier, IntegerLiteral(register_size))
        )

        context = _AngleEmissionContext(
            statements=statements,
            qubit_identifier=qubit_identifier,
            register_size=register_size,
            rotation_map=rotation_map,
            value_identifier=value_identifier,
            bounds=bounds,
        )
        self._emit_angle_statements(classical_input, context)

        statements.append(leqo_output("out", 0, qubit_identifier))
        return statements

    def _emit_angle_statements(
        self,
        classical_input: LeqoSupportedClassicalType,
        context: _AngleEmissionContext,
    ) -> None:
        if isinstance(classical_input, FloatType):
            self._emit_float_angle_statements(context)
            return

        if isinstance(classical_input, ArrayType):
            self._emit_array_angle_statements(context)
            return

        self._emit_generic_angle_statements(
            classical_input,
            context,
        )

    def _emit_float_angle_statements(self, context: _AngleEmissionContext) -> None:
        rotation_map = context.rotation_map
        statements = context.statements
        qubit_identifier = context.qubit_identifier

        if rotation_map is None:
            value_identifier = context.value_identifier
            assert value_identifier is not None

            factor = FloatLiteral(pi) if context.bounds == 1 else FloatLiteral(2.0)

            rotation_argument = BinaryExpression(
                BinaryOperator["*"],
                factor,
                value_identifier,
            )
            statements.append(
                QuantumGate(
                    modifiers=[],
                    name=Identifier("ry"),
                    arguments=[rotation_argument],
                    qubits=[qubit_identifier],
                    duration=None,
                )
            )
            return

        angle = rotation_map.get(0)
        if angle is None or angle == 0:
            return
        statements.append(
            QuantumGate(
                modifiers=[],
                name=Identifier("ry"),
                arguments=[FloatLiteral(2 * angle)],
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
            multiplier = FloatLiteral(2.0)
            for index in range(register_size):
                target = IndexedIdentifier(qubit_identifier, [[IntegerLiteral(index)]])
                value_expr = IndexExpression(
                    collection=value_identifier,
                    index=[IntegerLiteral(index)],
                )
                rotation_expr = BinaryExpression(
                    BinaryOperator["*"],
                    multiplier,
                    value_expr,
                )
                statements.append(
                    QuantumGate(
                        modifiers=[],
                        name=Identifier("ry"),
                        arguments=[rotation_expr],
                        qubits=[target],
                        duration=None,
                    )
                )
            return

        for index in range(register_size):
            angle = rotation_map.get(index)
            if angle is None:
                continue
            rotation_value = 2 * angle
            if rotation_value == 0:
                continue
            target = IndexedIdentifier(qubit_identifier, [[IntegerLiteral(index)]])
            statements.append(
                QuantumGate(
                    modifiers=[],
                    name=Identifier("ry"),
                    arguments=[FloatLiteral(rotation_value)],
                    qubits=[target],
                    duration=None,
                )
            )

    def _emit_generic_angle_statements(
        self,
        classical_input: LeqoSupportedClassicalType,
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
                target = IndexedIdentifier(qubit_identifier, [[IntegerLiteral(index)]])
                rotation_gate = QuantumGate(
                    modifiers=[],
                    name=Identifier("ry"),
                    arguments=[FloatLiteral(pi)],
                    qubits=[target],
                    duration=None,
                )
                statements.append(BranchingStatement(condition, [rotation_gate], []))
            return

        for index in sorted(rotation_map):
            angle = rotation_map[index]
            if angle == 0:
                continue
            target = IndexedIdentifier(qubit_identifier, [[IntegerLiteral(index)]])
            statements.append(
                QuantumGate(
                    modifiers=[],
                    name=Identifier("ry"),
                    arguments=[FloatLiteral(angle)],
                    qubits=[target],
                    duration=None,
                )
            )

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
                element = IndexExpression(
                    collection=value_identifier,
                    index=[IntegerLiteral(index)],
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
            case ArrayType() as array_type:
                element_size = array_type.element_type.size
                element_index = index // element_size
                bit_index = index % element_size

                element_expr = IndexExpression(
                    collection=value_identifier,
                    index=[IntegerLiteral(element_index)],
                )
                shifted = BinaryExpression(
                    BinaryOperator[">>"],
                    element_expr,
                    IntegerLiteral(bit_index),
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

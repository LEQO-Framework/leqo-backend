"""
Provides enricher strategy for enriching :class:`~app.model.CompileRequest.OperatorNode` from a database.
"""

from dataclasses import dataclass
from typing import cast, override

from openqasm3.ast import (
    Identifier,
    Include,
    IndexedIdentifier,
    IntegerLiteral,
    QuantumGate,
    QubitDeclaration,
    Statement,
)
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.enricher import Constraints, EnrichmentResult, ImplementationMetaData
from app.enricher.db_enricher import DataBaseEnricherStrategy
from app.enricher.exceptions import NoImplementationFound
from app.enricher.models import BaseNode, Input, InputType, NodeType, OperatorType
from app.enricher.models import OperatorNode as OperatorNodeTable
from app.enricher.utils import implementation, leqo_input, leqo_output
from app.model.CompileRequest import (
    ImplementationNode,
    OperatorNode,
)
from app.model.CompileRequest import (
    Node as FrontendNode,
)
from app.model.data_types import LeqoSupportedType, QubitType
from app.model.exceptions import InputCountMismatch, InputTypeMismatch


@dataclass(frozen=True)
class _AdditionOperand:
    """
    Helper structure describing an input register used by the generated adder.
    """

    name: str
    index: int
    declared_size: int | None
    effective_size: int


class OperatorEnricherStrategy(DataBaseEnricherStrategy):
    """
    Strategy capable of enriching :class:`~app.model.CompileRequest.OperatorNode` from a database.
    """

    def __init__(self, engine: AsyncEngine):
        super().__init__(engine)

    def _check_constraints(
        self, node: OperatorNode, requested_inputs: dict[int, LeqoSupportedType]
    ) -> None:
        """
        Checks the constraints of the node and requested inputs.

        :param node: The frontend node to check.
        :param requested_inputs: The requested inputs to check.
        :raises InputCountMismatch: If the number of requested inputs is not equal to 2
        :raises InputTypeMismatch: If the type of the requested inputs is not qubit.
        """
        if len(requested_inputs) != 2:  # noqa: PLR2004
            raise InputCountMismatch(
                node,
                actual=len(requested_inputs),
                should_be="equal",
                expected=2,
            )

        if not isinstance(requested_inputs[0], QubitType):
            raise InputTypeMismatch(
                node, 0, actual=requested_inputs[0], expected="qubit"
            )

        if not isinstance(requested_inputs[1], QubitType):
            raise InputTypeMismatch(
                node, 1, actual=requested_inputs[1], expected="qubit"
            )

    @override
    async def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> list[EnrichmentResult]:
        if isinstance(node, OperatorNode) and node.operator == "+":
            dynamic_exception: Exception | None = None
            if constraints is not None:
                try:
                    return [self._generate_addition_enrichment(node, constraints)]
                except (InputCountMismatch, InputTypeMismatch):
                    raise
                except Exception as exc:  # pragma: no cover - defensive fallback
                    dynamic_exception = exc

            try:
                db_results = await super()._enrich_impl(node, constraints)
            except InputCountMismatch:
                if constraints is not None:
                    raise
                db_results = []
            if db_results:
                return db_results

            fallback_results = await self._fetch_operator_without_size_constraints(
                node, constraints
            )
            if fallback_results:
                return fallback_results

            if dynamic_exception is not None:
                raise dynamic_exception

            if constraints is None:
                raise InputCountMismatch(
                    node,
                    actual=0,
                    should_be="equal",
                    expected=2,
                )

            return [self._generate_addition_enrichment(node, constraints)]

        return await super()._enrich_impl(node, constraints)

    def _generate_addition_enrichment(
        self, node: OperatorNode, constraints: Constraints
    ) -> EnrichmentResult:
        requested_inputs = constraints.requested_inputs
        self._check_constraints(node, requested_inputs)

        lhs = cast(QubitType, requested_inputs[0])
        rhs = cast(QubitType, requested_inputs[1])

        addend0 = _AdditionOperand(
            name="addend0",
            index=0,
            declared_size=lhs.size,
            effective_size=lhs.size or 1,
        )
        addend1 = _AdditionOperand(
            name="addend1",
            index=1,
            declared_size=rhs.size,
            effective_size=rhs.size or 1,
        )

        (
            statements,
            result_size,
            carry_count,
            depth,
        ) = self._build_addition_statements(
            addend0=addend0,
            addend1=addend1,
        )

        enriched_node = implementation(node, statements)
        width = (
            addend0.effective_size + addend1.effective_size + result_size + carry_count
        )
        return EnrichmentResult(
            enriched_node,
            ImplementationMetaData(width=width, depth=depth),
        )

    async def _fetch_operator_without_size_constraints(
        self, node: OperatorNode, constraints: Constraints | None
    ) -> list[EnrichmentResult]:
        Input0 = aliased(Input)
        Input1 = aliased(Input)

        query = cast(
            Select[tuple[BaseNode]],
            select(OperatorNodeTable)
            .join(Input0, OperatorNodeTable.inputs)
            .join(Input1, OperatorNodeTable.inputs)
            .where(
                OperatorNodeTable.type == NodeType(node.type),
                OperatorNodeTable.operator == OperatorType(node.operator),
                Input0.index == 0,
                Input0.type == InputType.QubitType,
                Input1.index == 1,
                Input1.type == InputType.QubitType,
            ),
        )

        query = query.options(selectinload(OperatorNodeTable.inputs))

        async with AsyncSession(self.engine) as session:
            result_nodes = (await session.execute(query)).unique().scalars().all()

        if not result_nodes:
            return []

        if constraints is not None:
            requested_inputs = constraints.requested_inputs

            filtered_nodes: list[BaseNode] = []
            for result_node in result_nodes:
                inputs_by_index = {
                    input_entry.index: input_entry for input_entry in result_node.inputs
                }

                lhs = inputs_by_index.get(0)
                rhs = inputs_by_index.get(1)
                if lhs is None or rhs is None:
                    continue

                lhs_request = requested_inputs.get(0)
                rhs_request = requested_inputs.get(1)
                if lhs_request is None or rhs_request is None:
                    continue

                if not isinstance(lhs_request, QubitType):
                    continue
                if not isinstance(rhs_request, QubitType):
                    continue

                if not self._input_satisfies_request(lhs, lhs_request):
                    continue
                if not self._input_satisfies_request(rhs, rhs_request):
                    continue

                filtered_nodes.append(result_node)

            result_nodes = filtered_nodes
            if not result_nodes:
                return []

        def sort_key(result_node: BaseNode) -> tuple[int | float, int | float]:
            return (
                result_node.width if result_node.width is not None else float("inf"),
                result_node.depth if result_node.depth is not None else float("inf"),
            )

        best_node = min(result_nodes, key=sort_key)
        implementation_value = best_node.implementation
        if implementation_value is None:
            raise NoImplementationFound(node)

        return [
            EnrichmentResult(
                ImplementationNode(id=node.id, implementation=implementation_value),
                ImplementationMetaData(
                    width=best_node.width,
                    depth=best_node.depth,
                ),
            )
        ]

    def _input_satisfies_request(self, db_input: Input, requested: QubitType) -> bool:
        if requested.size is None:
            return True
        if db_input.size is None:
            return True
        return db_input.size >= requested.size

    def _build_addition_statements(
        self,
        *,
        addend0: _AdditionOperand,
        addend1: _AdditionOperand,
    ) -> tuple[list[Statement], int, int, int]:
        max_bits = max(addend0.effective_size, addend1.effective_size)
        result_size = max_bits + 1
        carry_count = max(max_bits - 1, 0)

        statements: list[Statement] = [
            Include("stdgates.inc"),
            leqo_input(
                addend0.name,
                addend0.index,
                addend0.declared_size,
            ),
            leqo_input(
                addend1.name,
                addend1.index,
                addend1.declared_size,
            ),
        ]

        statements.append(
            QubitDeclaration(
                Identifier("sum"),
                IntegerLiteral(result_size),
            )
        )

        if carry_count > 0:
            statements.append(
                QubitDeclaration(
                    Identifier("carry"),
                    IntegerLiteral(carry_count),
                )
            )

        addend0_bits = self._build_qubit_references(
            addend0.name,
            addend0.declared_size,
            addend0.effective_size,
        )
        addend1_bits = self._build_qubit_references(
            addend1.name,
            addend1.declared_size,
            addend1.effective_size,
        )
        result_bits = self._build_qubit_references(
            "sum",
            result_size,
            result_size,
        )
        carry_bits = [
            self._qubit_reference("carry", index) for index in range(carry_count)
        ]

        gate_statements: list[Statement] = []
        depth = 0

        for index in range(max_bits):
            addend0_bit = addend0_bits[index] if index < len(addend0_bits) else None
            addend1_bit = addend1_bits[index] if index < len(addend1_bits) else None
            result_bit = result_bits[index]
            carry_in = carry_bits[index - 1] if index > 0 else None
            carry_out: Identifier | IndexedIdentifier

            carry_out = (
                carry_bits[index] if index < carry_count else result_bits[-1]
            )

            if addend0_bit is not None and addend1_bit is not None:
                gate_statements.append(
                    self._ccx_gate(addend0_bit, addend1_bit, carry_out)
                )
                depth += 1

            if carry_in is not None:
                if addend0_bit is not None:
                    gate_statements.append(
                        self._ccx_gate(carry_in, addend0_bit, carry_out)
                    )
                    depth += 1
                if addend1_bit is not None:
                    gate_statements.append(
                        self._ccx_gate(carry_in, addend1_bit, carry_out)
                    )
                    depth += 1

            if addend0_bit is not None:
                gate_statements.append(self._cx_gate(addend0_bit, result_bit))
                depth += 1
            if addend1_bit is not None:
                gate_statements.append(self._cx_gate(addend1_bit, result_bit))
                depth += 1
            if carry_in is not None:
                gate_statements.append(self._cx_gate(carry_in, result_bit))
                depth += 1

        statements.extend(gate_statements)
        statements.append(leqo_output("out", 0, Identifier("sum")))

        return statements, result_size, carry_count, depth

    def _build_qubit_references(
        self,
        name: str,
        declared_size: int | None,
        effective_size: int,
    ) -> list[Identifier | IndexedIdentifier]:
        if declared_size is None:
            return [self._qubit_reference(name, None)]

        return [self._qubit_reference(name, index) for index in range(effective_size)]

    def _qubit_reference(
        self, name: str, index: int | None
    ) -> Identifier | IndexedIdentifier:
        identifier = Identifier(name)
        if index is None:
            return identifier
        return IndexedIdentifier(
            identifier,
            [[IntegerLiteral(index)]],
        )

    def _cx_gate(
        self,
        control: Identifier | IndexedIdentifier,
        target: Identifier | IndexedIdentifier,
    ) -> QuantumGate:
        return QuantumGate(
            modifiers=[],
            name=Identifier("cx"),
            arguments=[],
            qubits=[control, target],
            duration=None,
        )

    def _ccx_gate(
        self,
        control1: Identifier | IndexedIdentifier,
        control2: Identifier | IndexedIdentifier,
        target: Identifier | IndexedIdentifier,
    ) -> QuantumGate:
        return QuantumGate(
            modifiers=[],
            name=Identifier("ccx"),
            arguments=[],
            qubits=[control1, control2, target],
            duration=None,
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
        if not isinstance(node, OperatorNode):
            return None
        self._check_constraints(node, requested_inputs)

        new_node = OperatorNodeTable(
            type=NodeType(node.type),
            depth=depth,
            width=width,
            implementation=implementation,
            operator=OperatorType(node.operator),
        )
        input_node0 = Input(
            index=0,
            type=InputType.QubitType,
            size=requested_inputs[0].size,
        )
        input_node1 = Input(
            index=1,
            type=InputType.QubitType,
            size=requested_inputs[1].size,
        )
        new_node.inputs.append(input_node0)
        new_node.inputs.append(input_node1)

        return new_node

    @override
    def _generate_query(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> Select[tuple[BaseNode]] | None:
        if not isinstance(node, OperatorNode):
            return None

        if constraints is None:
            raise InputCountMismatch(
                node,
                actual=0,
                should_be="equal",
                expected=2,
            )
        self._check_constraints(node, constraints.requested_inputs)

        Input0 = aliased(Input)
        Input1 = aliased(Input)

        return cast(
            Select[tuple[BaseNode]],
            select(OperatorNodeTable)
            .join(Input0, OperatorNodeTable.inputs)
            .join(Input1, OperatorNodeTable.inputs)
            .where(
                OperatorNodeTable.type == NodeType(node.type),
                OperatorNodeTable.operator == OperatorType(node.operator),
                Input0.index == 0,
                Input0.type == InputType.QubitType,
                Input0.size >= constraints.requested_inputs[0].size,
                Input1.index == 1,
                Input1.type == InputType.QubitType,
                Input1.size >= constraints.requested_inputs[1].size,
            ),
        )

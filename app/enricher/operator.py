"""
Provides enricher strategy for enriching :class:`~app.model.CompileRequest.OperatorNode` from a database.
"""

from typing import cast, override

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import aliased

from app.enricher import Constraints
from app.enricher.db_enricher import DataBaseEnricherStrategy
from app.enricher.models import BaseNode, Input, InputType, NodeType, OperatorType
from app.enricher.models import OperatorNode as OperatorNodeTable
from app.model.CompileRequest import (
    Node as FrontendNode,
)
from app.model.CompileRequest import (
    OperatorNode,
)
from app.model.data_types import LeqoSupportedType, QubitType
from app.model.exceptions import InputCountMismatch, InputTypeMismatch


class OperatorEnricherStrategy(DataBaseEnricherStrategy):
    """
    Strategy capable of enriching :class:`~app.model.CompileRequest.OperatorNode` from a database.
    """

    def __init__(self, engine: AsyncEngine):
        super().__init__(engine)

    def _check_constraints(
        self, node: OperatorNode, requested_inputs: dict[int, LeqoSupportedType]
    ) -> None:
        """Checks the constraints of the node and requested inputs.

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

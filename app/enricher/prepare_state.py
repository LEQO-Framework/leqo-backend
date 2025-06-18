"""
Provides enricher strategy for enriching :class:`~app.model.CompileRequest.PrepareStateNode` from a database.
"""

from typing import cast, override

from sqlalchemy import Select, exists, select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.enricher import Constraints
from app.enricher.db_enricher import DataBaseEnricherStrategy
from app.enricher.exceptions import (
    PrepareStateSizeOutOfRange,
    QuantumStateNotSupported,
)
from app.enricher.models import BaseNode, Input, NodeType, QuantumStateType
from app.enricher.models import PrepareStateNode as PrepareStateTable
from app.model.CompileRequest import (
    Node as FrontendNode,
)
from app.model.CompileRequest import (
    PrepareStateNode,
)
from app.model.data_types import LeqoSupportedType
from app.model.exceptions import InputCountMismatch


class PrepareStateEnricherStrategy(DataBaseEnricherStrategy):
    """
    Strategy capable of enriching :class:`~app.model.CompileRequest.PrepareStateNode` from a database.
    """

    def __init__(self, engine: AsyncEngine):
        super().__init__(engine)

    def _check_constraints(
        self, node: PrepareStateNode, requested_inputs: dict[int, LeqoSupportedType]
    ) -> None:
        """Checks the constraints of the node and requested inputs.

        :param node: The frontend node to check.
        :param requested_inputs: The requested inputs to check.
        :raises QuantumStateNotSupported: If the quantum state is not supported.
        :raises PrepareStateSizeOutOfRange: If the size of the state is less than or equal to 0.
        :raises InputCountMismatch: If the number of requested inputs is not equal to 0.
        """
        if node.quantumState == "custom":
            raise QuantumStateNotSupported(node)

        if node.size <= 0:
            raise PrepareStateSizeOutOfRange(node)

        if len(requested_inputs) != 0:
            raise InputCountMismatch(
                node,
                actual=len(requested_inputs),
                should_be="equal",
                expected=0,
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
        if not isinstance(node, PrepareStateNode):
            return None
        self._check_constraints(node, requested_inputs)

        return PrepareStateTable(
            type=NodeType(node.type),
            depth=depth,
            width=width,
            implementation=implementation,
            quantumState=QuantumStateType(node.quantumState),
            size=node.size,
        )

    @override
    def _generate_query(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> Select[tuple[BaseNode]] | None:
        if not isinstance(node, PrepareStateNode):
            return None

        if node.quantumState == "custom":
            raise QuantumStateNotSupported(node)

        if node.size <= 0:
            raise PrepareStateSizeOutOfRange(node)

        if constraints is None or len(constraints.requested_inputs) != 0:
            raise InputCountMismatch(
                node,
                actual=len(constraints.requested_inputs) if constraints else 0,
                should_be="equal",
                expected=0,
            )

        no_inputs = ~exists().where(Input.node_id == PrepareStateTable.id)
        return cast(
            Select[tuple[BaseNode]],
            select(PrepareStateTable).where(
                PrepareStateTable.type == NodeType(node.type),
                no_inputs,
                PrepareStateTable.quantum_state == QuantumStateType(node.quantumState),
                PrepareStateTable.size == node.size,
            ),
        )

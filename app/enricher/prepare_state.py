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
from app.model.exceptions import InputCountMismatch


class PrepareStateEnricherStrategy(DataBaseEnricherStrategy):
    """
    Strategy capable of enriching :class:`~app.model.CompileRequest.PrepareStateNode` from a database.
    """

    def __init__(self, engine: AsyncEngine):
        super().__init__(engine)

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

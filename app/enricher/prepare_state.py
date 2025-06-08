"""
Provides enricher strategy for enriching :class:`~app.model.CompileRequest.PrepareStateNode` from a database.
"""

from typing import cast, override

from sqlalchemy import Select, exists, select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.enricher import (
    Constraints,
    ConstraintValidationException,
    InputValidationException,
)
from app.enricher.db_enricher import DataBaseEnricherStrategy
from app.model.CompileRequest import (
    Node as FrontendNode,
)
from app.model.CompileRequest import (
    PrepareStateNode,
)
from app.model.database_model import BaseNode, Input, NodeType, QuantumStateType
from app.model.database_model import PrepareStateNode as PrepareStateTable


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

        if node.quantumState == "custom" or node.size <= 0:
            raise InputValidationException(
                "Custom prepare state or size below 1 are not supported"
            )

        if constraints is None or len(constraints.requested_inputs) != 0:
            raise ConstraintValidationException("PrepareStateNode can't have an input")

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

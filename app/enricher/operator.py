"""
Provides enricher strategy for enriching :class:`~app.model.CompileRequest.OperatorNode` from a database.
"""

from typing import cast, override

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import aliased

from app.enricher import (
    Constraints,
    ConstraintValidationException,
)
from app.enricher.db_enricher import DataBaseEnricherStrategy
from app.model.CompileRequest import (
    Node as FrontendNode,
)
from app.model.CompileRequest import (
    OperatorNode,
)
from app.model.data_types import QubitType
from app.model.database_model import BaseNode, Input, InputType, NodeType, OperatorType
from app.model.database_model import OperatorNode as OperatorNodeTable


class OperatorEnricherStrategy(DataBaseEnricherStrategy):
    """
    Strategy capable of enriching :class:`~app.model.CompileRequest.OperatorNode` from a database.
    """

    def __init__(self, engine: AsyncEngine):
        super().__init__(engine)

    @override
    def _generate_query(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> Select[tuple[BaseNode]] | None:
        if not isinstance(node, OperatorNode):
            return None

        if constraints is None or len(constraints.requested_inputs) != 2:  # noqa: PLR2004
            raise ConstraintValidationException(
                "OperatorNode can only have a two inputs"
            )

        if not isinstance(constraints.requested_inputs[0], QubitType) or not isinstance(
            constraints.requested_inputs[1], QubitType
        ):
            raise ConstraintValidationException(
                "OperatorNode only supports qubit types"
            )

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
                Input0.size == constraints.requested_inputs[0].size,
                Input1.index == 1,
                Input1.type == InputType.QubitType,
                Input1.size == constraints.requested_inputs[1].size,
            ),
        )

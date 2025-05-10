"""
Provides enricher strategy for enriching :class:`~app.model.CompileRequest.OperatorNode` from a database.
"""

from typing import override

from sqlalchemy import and_, select

from app.enricher import (
    Constraints,
    ConstraintValidationException,
    EnricherStrategy,
    EnrichmentResult,
    ImplementationMetaData,
    NodeUnsupportedException,
)
from app.enricher.engine import DatabaseEngine
from app.enricher.models import BaseNode as BaseNodeTable
from app.enricher.models import InputType
from app.enricher.models import OperatorNode as OperatorNodeTable
from app.enricher.utils import implementation
from app.model.CompileRequest import (
    Node as FrontendNode,
)
from app.model.CompileRequest import OperatorNode
from app.model.data_types import QubitType


class OperatorEnricherStrategy(EnricherStrategy):
    """
    Strategy capable of enriching :class:`~app.model.CompileRequest.OperatorNode` from a database.
    """

    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> EnrichmentResult:
        if not isinstance(node, OperatorNode):
            raise NodeUnsupportedException(node)

        if constraints is None or len(constraints.requested_inputs) != 2:
            raise ConstraintValidationException(
                "OperatorNode can only have a two inputs"
            )

        if not isinstance(constraints.requested_inputs[0], QubitType):
            raise ConstraintValidationException(
                "OperatorNode only supports qubit types"
            )

        databaseEngine = DatabaseEngine()
        session = databaseEngine._get_database_session()
        query = (
            select(OperatorNodeTable)
            .join(BaseNodeTable, OperatorNodeTable.id == BaseNodeTable.id)
            .where(
                and_(
                    OperatorNodeTable.type == node.type,
                    OperatorNodeTable.depth <= constraints.optimizeDepth,
                    OperatorNodeTable.width <= constraints.optimizeWidth,
                    OperatorNodeTable.inputs.in_(
                        [
                            InputType.QubitType
                        ]
                    ),
                    OperatorNodeTable.operator == node.operator
                )
            )
        )

        result_data = session.execute(query).scalars().first()

        if result_data is None:
            raise NodeUnsupportedException(node)

        return EnrichmentResult(
            implementation(
                node,
                [
                    # convert implementation into program ????
                ],
            ),
            ImplementationMetaData(width=result_data.width, depth=result_data.depth),
        )

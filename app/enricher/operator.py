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
    ImplementationNode,
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

        if constraints is None or len(constraints.requested_inputs) != 2:  # noqa: PLR2004
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
                    OperatorNodeTable.inputs == [
                        {
                            "index": 0,
                            "type": InputType.QubitType.value,
                            "size": constraints.requested_inputs[0].reg_size,
                        },
                        {
                            "index": 1,
                            "type": InputType.QubitType.value,
                            "size": constraints.requested_inputs[1].reg_size,
                        },
                    ],
                    OperatorNodeTable.operator == node.operator,
                )
            )
        )

        result_nodes = session.execute(query).scalars().all()
        session.close()

        if not result_nodes:
            raise NodeUnsupportedException(node)

        enrichment_results = []
        for node in result_nodes:
            enrichment_results.append(
                EnrichmentResult(
                    ImplementationNode(
                        id=node.id,
                        implementation=node.implementation
                    ),
                    ImplementationMetaData(width=node.width, depth=node.depth),
                )
            )
            
        return enrichment_results

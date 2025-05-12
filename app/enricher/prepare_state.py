"""
Provides enricher strategy for enriching :class:`~app.model.CompileRequest.PrepareStateNode` from a database.
"""

from typing import override

from sqlalchemy import and_, select

from app.enricher import (
    Constraints,
    ConstraintValidationException,
    EnricherStrategy,
    EnrichmentResult,
    ImplementationMetaData,
    InputValidationException,
    NodeUnsupportedException,
)
from app.enricher.engine import DatabaseEngine
from app.enricher.models import BaseNode as BaseNodeTable
from app.enricher.models import PrepareStateNode as PrepareStateTable
from app.enricher.utils import implementation
from app.model.CompileRequest import (
    ImplementationNode,
    Node as FrontendNode,
)
from app.model.CompileRequest import (
    PrepareStateNode,
)


class PrepareStateEnricherStrategy(EnricherStrategy):
    """
    Strategy capable of enriching :class:`~app.model.CompileRequest.PrepareStateNode` from a database.
    """

    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> EnrichmentResult:
        if not isinstance(node, PrepareStateNode):
            raise NodeUnsupportedException(node)

        if node.quantumState == "custom" or node.size <= 0:
            raise InputValidationException(
                "Custom prepare state or size below 1 are not supported"
            )

        if (
            constraints is None or len(constraints.requested_inputs) != 0
        ):
            raise ConstraintValidationException("PrepareStateNode can't have an input")

        databaseEngine = DatabaseEngine()
        session = databaseEngine._get_database_session()
        query = (
            select(PrepareStateTable)
            .join(BaseNodeTable, PrepareStateTable.id == BaseNodeTable.id)
            .where(
                and_(
                    PrepareStateTable.type == node.type,
                    PrepareStateTable.depth <= constraints.optimizeDepth,
                    PrepareStateTable.width <= constraints.optimizeWidth,
                    PrepareStateTable.inputs == [],
                    PrepareStateTable.size == node.size,
                    PrepareStateTable.quantum_state == node.quantumState,
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

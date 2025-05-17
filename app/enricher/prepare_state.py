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
from app.enricher.models import NodeType, QuantumStateType
from app.enricher.models import PrepareStateNode as PrepareStateTable
from app.model.CompileRequest import (
    ImplementationNode,
    PrepareStateNode,
)
from app.model.CompileRequest import (
    Node as FrontendNode,
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

        if node.quantumState == "custom":
            raise InputValidationException(
                "Custom prepare state or size below 1 are not supported"
            )

        if constraints is None or len(constraints.requested_inputs) != 0:
            raise ConstraintValidationException("PrepareStateNode can't have an input")

        databaseEngine = DatabaseEngine()
        session = databaseEngine._get_database_session()
        query = select(PrepareStateTable).where(
            and_(
                PrepareStateTable.type == NodeType(node.type),
                PrepareStateTable.inputs == [],
                PrepareStateTable.quantum_state == QuantumStateType(node.quantumState),
            )
        )

        result_nodes = session.execute(query).scalars().all()
        session.close()

        if not result_nodes:
            raise RuntimeError("No results found in the database")

        enrichment_results = []
        for result_node in result_nodes:
            if result_node.implementation is None:
                raise NodeUnsupportedException(node)

            enrichment_results.append(
                EnrichmentResult(
                    ImplementationNode(
                        id=node.id, implementation=result_node.implementation
                    ),
                    ImplementationMetaData(
                        width=result_node.width, depth=result_node.depth
                    ),
                )
            )

        return enrichment_results

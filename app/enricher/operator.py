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
from app.enricher.models import InputType, NodeType, OperatorType
from app.enricher.models import OperatorNode as OperatorNodeTable
from app.model.CompileRequest import (
    ImplementationNode,
    OperatorNode,
)
from app.model.CompileRequest import (
    Node as FrontendNode,
)
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

        if not isinstance(constraints.requested_inputs[0], QubitType) or not isinstance(
            constraints.requested_inputs[1], QubitType
        ):
            raise ConstraintValidationException(
                "OperatorNode only supports qubit types"
            )

        databaseEngine = DatabaseEngine()
        session = databaseEngine._get_database_session()
        query = select(OperatorNodeTable).where(
            and_(
                OperatorNodeTable.type == NodeType(node.type),
                OperatorNodeTable.inputs
                == [
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
                OperatorNodeTable.operator == OperatorType(node.operator),
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

"""
Provides enricher strategy for enriching :class:`~app.model.CompileRequest.EncodeValueNode` from a database.
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
from app.enricher.models import EncodeValueNode as EncodeNodeTable
from app.enricher.models import InputType
from app.enricher.utils import implementation
from app.model.CompileRequest import (
    EncodeValueNode,
)
from app.model.CompileRequest import (
    Node as FrontendNode,
)
from app.model.data_types import LeqoSupportedClassicalType


# ToDo: bound and size are unclear
class EncodeValueEnricherStrategy(EnricherStrategy):
    """
    Strategy capable of enriching :class:`~app.model.CompileRequest.EncodeValueNode` from a database.
    """

    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> EnrichmentResult:
        if not isinstance(node, EncodeValueNode):
            raise NodeUnsupportedException(node)
        
        if node.encoding == 'custom' or node.bounds <= 0:
            raise InputValidationException(
                "Custom encoding or bounds below 1 are not supported"
            )
        
        if (
            constraints is None or len(constraints.requested_inputs) != 1
        ):  # How do Ancilla nodes count
            raise ConstraintValidationException(
                "EncodeValueNode can only have a single input"
            )

        if not isinstance(constraints.requested_inputs[0], LeqoSupportedClassicalType):
            raise ConstraintValidationException(
                "EncodeValueNode only supports classical types"
            )

        databaseEngine = DatabaseEngine()
        session = databaseEngine._get_database_session()
        query = (
            select(EncodeNodeTable)
            .join(BaseNodeTable, EncodeNodeTable.id == BaseNodeTable.id)
            .where(
                and_(
                    EncodeNodeTable.type == node.type,
                    EncodeNodeTable.depth <= constraints.optimizeDepth,
                    EncodeNodeTable.width <= constraints.optimizeWidth,
                    EncodeNodeTable.inputs.in_(
                        [
                            InputType.IntType,
                            InputType.FloatType,
                            InputType.BoolType,
                            InputType.BitType,
                        ]
                    ),
                    EncodeNodeTable.encoding == node.encoding,
                    EncodeNodeTable.bounds == node.bounds,
                )
            )
        )

        result_data = session.execute(query).scalars().first()
        session.close()

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

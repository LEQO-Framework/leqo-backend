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

        if constraints is None or len(constraints.requested_inputs) != 1:
            raise ConstraintValidationException(
                "EncodeValue can only have a single input"
            )

        if not isinstance(constraints.requested_inputs[0], LeqoSupportedClassicalType):
            raise ConstraintValidationException(
                "EncodeValue only supports classical types"
            )

        input_size = constraints.requested_inputs[0].bit_size

        databaseEngine = DatabaseEngine()
        session = databaseEngine._get_database_session()
        query = (
            select(EncodeNodeTable)
            .join(BaseNodeTable, EncodeNodeTable.id == BaseNodeTable.id)
            .where(
                and_(
                    BaseNodeTable.type == node.type,
                    BaseNodeTable.depth >= constraints.optimizeDepth,
                    BaseNodeTable.width >= constraints.optimizeWidth,
                    BaseNodeTable.inputs.in_(
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

        if result_data is None:
            raise NodeUnsupportedException(node)

        return EnrichmentResult(
            implementation(
                node,
                [
                    # ?????????????
                ],
            ),
            ImplementationMetaData(width=result_data.width, depth=result_data.depth),
        )

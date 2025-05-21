"""
Provides enricher strategy for enriching :class:`~app.model.CompileRequest.EncodeValueNode` from a database.
"""

from typing import override

from sqlalchemy import select

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
from app.enricher.models import EncodeValueNode as EncodeNodeTable
from app.enricher.models import EncodingType, Input, InputType, NodeType
from app.model.CompileRequest import (
    EncodeValueNode,
    ImplementationNode,
)
from app.model.CompileRequest import (
    Node as FrontendNode,
)
from app.model.data_types import LeqoSupportedClassicalType, LeqoSupportedType


class EncodeValueEnricherStrategy(EnricherStrategy):
    """
    Strategy capable of enriching :class:`~app.model.CompileRequest.EncodeValueNode` from a database.
    """

    def _convert_to_input_type(self, node_type: LeqoSupportedType) -> str:
        """
        Converts the node type to the enum value of :class:`~app.enricher.models.InputType`
        """
        match type(node_type).__name__:
            case "IntType":
                input_type = InputType.IntType.value
            case "FloatType":
                input_type = InputType.FloatType.value
            case "BitType":
                input_type = InputType.BitType.value
            case "BoolType":
                input_type = InputType.BoolType.value
            case "QubitType":
                input_type = InputType.QubitType.value
            case _:
                raise ConstraintValidationException(f"Unsupported input type: {input}")

        return input_type

    @override
    async def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> list[EnrichmentResult]:
        if not isinstance(node, EncodeValueNode):
            return []

        if node.encoding == "custom":
            raise InputValidationException("Custom encoding is not supported")

        if node.bounds < 0 or node.bounds > 1:
            raise InputValidationException("Bounds must be between 0 and 1")

        if constraints is None or len(constraints.requested_inputs) != 1:
            raise ConstraintValidationException(
                "EncodeValueNode can only have a single input"
            )

        if not isinstance(constraints.requested_inputs[0], LeqoSupportedClassicalType):
            raise ConstraintValidationException(
                "EncodeValueNode only supports classical types"
            )

        converted_input_type = self._convert_to_input_type(
            constraints.requested_inputs[0]
        )

        databaseEngine = DatabaseEngine()
        session = databaseEngine.get_database_session()
        query = (
            select(EncodeNodeTable)
            .join(Input, EncodeNodeTable.inputs)
            .where(
                EncodeNodeTable.type == NodeType(node.type),
                EncodeNodeTable.encoding == EncodingType(node.encoding),
                EncodeNodeTable.bounds == node.bounds,
                Input.index == 0,
                Input.type == converted_input_type,
                Input.size == constraints.requested_inputs[0].bit_size,
            )
        )

        async with session:
            result_nodes = (await session.execute(query)).scalars().all()

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

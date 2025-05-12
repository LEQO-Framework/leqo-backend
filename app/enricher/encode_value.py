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
from app.model.CompileRequest import (
    EncodeValueNode,
    ImplementationNode,
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
    
    def _convert_requested_inputs_to_json(self, requested_inputs: dict[int, LeqoSupportedClassicalType]) -> list[dict[str, int | str | None]]:
        """
        Converts the requested inputs to the required JSON object.
        """
        inputsTransformedToJSON = []
        for index, input in requested_inputs.items():
            match input.__name__:
                case "IntType":
                    input_type = InputType.IntType.value
                    size = input.bit_size
                case "FloatType":
                    input_type = InputType.FloatType.value
                    size = input.bit_size
                case "BitType":
                    input_type = InputType.BitType.value
                    size = input.bit_size
                case "BoolType":
                    input_type = InputType.BoolType.value
                    size = None
                case "QubitType":
                    input_type = InputType.QubitType.value
                    size = input.reg_size
                case _:
                    raise ConstraintValidationException(f"Unsupported input type: {input}")

            inputsTransformedToJSON.append({
                "index": index,
                "type": input_type,
                "size": size
            })
            
        return inputsTransformedToJSON

    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> EnrichmentResult:
        if not isinstance(node, EncodeValueNode):
            raise NodeUnsupportedException(node)

        if node.encoding == "custom" or node.bounds <= 0:
            raise InputValidationException(
                "Custom encoding or bounds below 1 are not supported"
            )

        if (
            constraints is None or len(constraints.requested_inputs) != 1
        ):
            raise ConstraintValidationException(
                "EncodeValueNode can only have a single input"
            )

        if not isinstance(constraints.requested_inputs[0], LeqoSupportedClassicalType):
            raise ConstraintValidationException(
                "EncodeValueNode only supports classical types"
            )
            
        inputsTransformedToJSON = self._convert_requested_inputs_to_json(constraints.requested_inputs)

        databaseEngine = DatabaseEngine()
        session = databaseEngine._get_database_session()
        query = (
            select(EncodeNodeTable)
            .join(BaseNodeTable, EncodeNodeTable.id == BaseNodeTable.id)
            .where(
                and_(
                    EncodeNodeTable.type == node.type,
                    EncodeNodeTable.inputs == inputsTransformedToJSON,
                    EncodeNodeTable.encoding == node.encoding,
                    EncodeNodeTable.bounds == node.bounds,
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

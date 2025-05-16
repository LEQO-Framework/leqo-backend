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
from app.enricher.models import EncodeValueNode as EncodeNodeTable
from app.enricher.models import EncodingType, InputType, NodeType
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

    def _convert_requested_inputs_to_json(
        self, requested_inputs: dict[int, LeqoSupportedType]
    ) -> list[dict[str, object]]:
        """
        Converts the requested inputs to the required JSON object.
        """
        inputsTransformedToJSON = []
        size: int | None = None
        for index, input in requested_inputs.items():
            match type(input).__name__:
                case "IntType":
                    input_type = InputType.IntType.value
                    size = getattr(input, "bit_size", None)
                case "FloatType":
                    input_type = InputType.FloatType.value
                    size = getattr(input, "bit_size", None)
                case "BitType":
                    input_type = InputType.BitType.value
                    size = getattr(input, "bit_size", None)
                case "BoolType":
                    input_type = InputType.BoolType.value
                    size = None
                case "QubitType":
                    input_type = InputType.QubitType.value
                    size = getattr(input, "reg_size", None)
                case _:
                    raise ConstraintValidationException(
                        f"Unsupported input type: {input}"
                    )

            inputsTransformedToJSON.append(
                {"index": index, "type": input_type, "size": size}
            )

        return inputsTransformedToJSON

    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> EnrichmentResult:
        if not isinstance(node, EncodeValueNode):
            raise NodeUnsupportedException(node)

        if node.encoding == "custom" or node.bounds < 0:
            raise InputValidationException(
                "Custom encoding or bounds below 0 are not supported"
            )

        if constraints is None or len(constraints.requested_inputs) != 1:
            raise ConstraintValidationException(
                "EncodeValueNode can only have a single input"
            )

        if not isinstance(constraints.requested_inputs[0], LeqoSupportedClassicalType):
            raise ConstraintValidationException(
                "EncodeValueNode only supports classical types"
            )

        inputsTransformedToJSON = self._convert_requested_inputs_to_json(
            constraints.requested_inputs
        )

        databaseEngine = DatabaseEngine()
        session = databaseEngine._get_database_session()
        query = select(EncodeNodeTable).where(
            and_(
                EncodeNodeTable.type == NodeType(node.type),
                EncodeNodeTable.inputs == inputsTransformedToJSON,
                EncodeNodeTable.encoding == EncodingType(node.encoding),
                EncodeNodeTable.bounds == node.bounds,
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

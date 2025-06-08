"""
Provides enricher strategy for enriching :class:`~app.model.CompileRequest.EncodeValueNode` from a database.
"""

from typing import cast, override

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.enricher import (
    Constraints,
    ConstraintValidationException,
    InputValidationException,
)
from app.enricher.db_enricher import DataBaseEnricherStrategy
from app.model.CompileRequest import (
    EncodeValueNode,
)
from app.model.CompileRequest import (
    Node as FrontendNode,
)
from app.model.data_types import (
    BitType,
    BoolType,
    FloatType,
    IntType,
    LeqoSupportedClassicalType,
    LeqoSupportedType,
    QubitType,
)
from app.model.database_model import BaseNode, EncodingType, Input, InputType, NodeType
from app.model.database_model import EncodeValueNode as EncodeNodeTable


class EncodeValueEnricherStrategy(DataBaseEnricherStrategy):
    """
    Strategy capable of enriching :class:`~app.model.CompileRequest.EncodeValueNode` from a database.
    """

    def __init__(self, engine: AsyncEngine):
        super().__init__(engine)

    def _convert_to_input_type(self, node_type: LeqoSupportedType) -> str:
        """
        Converts the node type to the enum value of :class:`~app.enricher.models.InputType`
        """
        match node_type:
            case IntType():
                input_type = InputType.IntType.value
            case FloatType():
                input_type = InputType.FloatType.value
            case BitType():
                input_type = InputType.BitType.value
            case BoolType():
                input_type = InputType.BoolType.value
            case QubitType():
                input_type = InputType.QubitType.value
            case _:
                raise ConstraintValidationException(f"Unsupported input type: {input}")

        return input_type

    @override
    def _generate_query(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> Select[tuple[BaseNode]] | None:
        if not isinstance(node, EncodeValueNode):
            return None

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

        return cast(
            Select[tuple[BaseNode]],
            select(EncodeNodeTable)
            .join(Input, EncodeNodeTable.inputs)
            .where(
                EncodeNodeTable.type == NodeType(node.type),
                EncodeNodeTable.encoding == EncodingType(node.encoding),
                EncodeNodeTable.bounds == node.bounds,
                Input.index == 0,
                Input.type == converted_input_type,
                Input.size == constraints.requested_inputs[0].size,
            ),
        )

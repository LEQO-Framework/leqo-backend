"""
Provides enricher strategy for enriching :class:`~app.model.CompileRequest.EncodeValueNode` from a database.
"""

from typing import cast, override

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.enricher import Constraints
from app.enricher.db_enricher import DataBaseEnricherStrategy
from app.enricher.exceptions import BoundsOutOfRange, EncodingNotSupported
from app.enricher.models import BaseNode, EncodingType, Input, InputType, NodeType
from app.enricher.models import EncodeValueNode as EncodeNodeTable
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
from app.model.exceptions import InputCountMismatch, InputTypeMismatch


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
                raise RuntimeError(f"Unsupported input type: {input}")

        return input_type

    def _check_constraints(
        self, node: EncodeValueNode, requested_inputs: dict[int, LeqoSupportedType]
    ) -> None:
        """
        Checks the constraints for the node and requested inputs.
        Raises exceptions if constraints are not met.

        :param node: The node to check constraints for.
        :param requested_inputs: Dictionary where the key is the input index and value the type of the node.
        :raises EncodingNotSupported: If the encoding is not supported.
        :raises BoundsOutOfRange: If the bounds are out of range.
        :raises InputCountMismatch: If the number of requested inputs does not match the expected count.
        :raises InputTypeMismatch: If the type of the requested input does not match the expected type.
        """
        if node.encoding == "custom":
            raise EncodingNotSupported(node)

        if node.bounds < 0 or node.bounds > 1:
            raise BoundsOutOfRange(node)

        if len(requested_inputs) != 1:
            raise InputCountMismatch(
                node,
                actual=len(requested_inputs),
                should_be="equal",
                expected=1,
            )

        if not isinstance(requested_inputs[0], LeqoSupportedClassicalType):
            raise InputTypeMismatch(
                node,
                input_index=0,
                actual=requested_inputs[0],
                expected="classical",
            )

    @override
    def _generate_database_node(
        self,
        node: FrontendNode,
        implementation: str,
        requested_inputs: dict[int, LeqoSupportedType],
        width: int,
        depth: int | None,
    ) -> BaseNode | None:
        if not isinstance(node, EncodeValueNode):
            return None
        self._check_constraints(node, requested_inputs)

        converted_input_type = self._convert_to_input_type(requested_inputs[0])

        new_node = EncodeNodeTable(
            type=NodeType(node.type),
            depth=depth,
            width=width,
            implementation=implementation,
            encoding=EncodingType(node.encoding),
            bounds=node.bounds,
        )
        input_node = Input(
            index=0,
            type=converted_input_type,
            size=requested_inputs[0].size,
        )
        new_node.inputs.append(input_node)

        return new_node

    @override
    def _generate_query(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> Select[tuple[BaseNode]] | None:
        if not isinstance(node, EncodeValueNode):
            return None

        if constraints is None:
            raise InputCountMismatch(
                node,
                actual=0,
                should_be="equal",
                expected=1,
            )

        self._check_constraints(node, constraints.requested_inputs)

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
                Input.size >= constraints.requested_inputs[0].size,
            ),
        )

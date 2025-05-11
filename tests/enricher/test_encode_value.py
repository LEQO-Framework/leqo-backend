import asyncio
from typing import override

import pytest

from app.enricher import (
    Constraints,
    ConstraintValidationException,
    EnricherStrategy,
    EnrichmentResult,
    ImplementationMetaData,
    InputValidationException,
    NodeUnsupportedException,
)
from app.enricher.encode_value import EncodeValueEnricherStrategy
from app.enricher.engine import DatabaseEngine
from app.enricher.models import EncodeValueNode, EncodingType, InputType, NodeType
from app.model.CompileRequest import (
    BitLiteralNode,
    ImplementationNode,
)
from app.model.CompileRequest import EncodeValueNode as FrontendEncodeValueNode
from app.model.CompileRequest import (
    Node as FrontendNode,
)
from app.model.CompileRequest import PrepareStateNode as FrontendPrepareStateNode
from app.model.data_types import FloatType, IntType, QubitType


@pytest.fixture
async def initialise_database() -> None:
    databaseEngine = DatabaseEngine()
    session = databaseEngine._get_database_session()

    node1 = EncodeValueNode(
        type=NodeType.ENCODE,
        depth=1,
        width=1,
        implementation="amplitude_impl",
        inputs=[InputType.FloatType],
        encoding=EncodingType.AMPLITUDE,
        bounds=2,
    )
    node2 = EncodeValueNode(
        type=NodeType.ENCODE,
        depth=2,
        width=2,
        implementation="angle_impl",
        inputs=[InputType.FloatType],
        encoding=EncodingType.ANGLE,
        bounds=4,
    )
    node3 = EncodeValueNode(
        type=NodeType.ENCODE,
        depth=3,
        width=3,
        implementation="matrix_impl",
        inputs=[InputType.BitType],
        encoding=EncodingType.MATRIX,
        bounds=6,
    )
    node4 = EncodeValueNode(
        type=NodeType.ENCODE,
        depth=4,
        width=4,
        implementation="schimdt_impl",
        inputs=[InputType.BoolType],
        encoding=EncodingType.SCHMIDT,
        bounds=8,
    )

    session.add_all([node1, node2, node3, node4])
    session.commit()
    session.close()


@pytest.mark.asyncio
async def reset_database() -> None:
    # reset the database
    pass


@pytest.mark.asyncio
async def test_enrich_amplitude_encode_value() -> None:
    node = FrontendEncodeValueNode(
        id="1",
        label=None,
        type="encode",
        encoding="amplitude",
        bounds=2,
    )
    constraints = Constraints(
        requested_inputs={1: FloatType(bit_size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    strategy = EncodeValueEnricherStrategy()
    result = await strategy.enrich(node, constraints)

    assert result is not None
    # assert implementation
    assert result.meta.width == 1
    assert result.meta.depth == 1


@pytest.mark.asyncio
async def test_enrich_angle_encode_value() -> None:
    node = FrontendEncodeValueNode(
        id="2",
        label=None,
        type="encode",
        encoding="angle",
        bounds=4,
    )
    constraints = Constraints(
        requested_inputs={2: FloatType(bit_size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    strategy = EncodeValueEnricherStrategy()
    result = await strategy.enrich(node, constraints)

    assert result is not None
    # assert implementation
    assert result.meta.width == 2
    assert result.meta.depth == 2


@pytest.mark.asyncio
async def test_enrich_matrix_encode_value() -> None:
    node = FrontendEncodeValueNode(
        id="3",
        label=None,
        type="encode",
        encoding="matrix",
        bounds=6,
    )
    constraints = Constraints(
        requested_inputs={3: FloatType(bit_size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    strategy = EncodeValueEnricherStrategy()
    result = await strategy.enrich(node, constraints)

    assert result is not None
    # assert implementation
    # assert uncompute implementation
    assert result.meta.width == 3
    assert result.meta.depth == 3


@pytest.mark.asyncio
async def test_enrich_schmidt_encode_value() -> None:
    node = FrontendEncodeValueNode(
        id="4",
        label=None,
        type="encode",
        encoding="schmidt",
        bounds=8,
    )
    constraints = Constraints(
        requested_inputs={4: FloatType(bit_size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    strategy = EncodeValueEnricherStrategy()
    result = await strategy.enrich(node, constraints)

    assert result is not None
    # assert implementation
    assert result.meta.width == 4
    assert result.meta.depth == 4


@pytest.mark.asyncio
async def test_enrich_custom_encode_value() -> None:
    node = FrontendEncodeValueNode(
        id="4",
        label=None,
        type="encode",
        encoding="custom",
        bounds=8,
    )
    constraints = Constraints(
        requested_inputs={1: FloatType(bit_size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )
    strategy = EncodeValueEnricherStrategy()

    with pytest.raises(
        InputValidationException,
        match=r"^Custom encoding or bounds below 1 are not supported$",
    ):
        await strategy.enrich(node, constraints)


@pytest.mark.asyncio
async def test_enrich_encode_value_bound_zero() -> None:
    node = FrontendEncodeValueNode(
        id="4",
        label=None,
        type="encode",
        encoding="matrix",
        bounds=0,
    )
    constraints = Constraints(
        requested_inputs={1: FloatType(bit_size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    strategy = EncodeValueEnricherStrategy()
    with pytest.raises(
        InputValidationException,
        match=r"^Custom encoding or bounds below 1 are not supported$",
    ):
        await strategy.enrich(node, constraints)


@pytest.mark.asyncio
async def test_enrich_unknown_node() -> None:
    node = FrontendPrepareStateNode(
        id="4", label=None, type="prepare", size=3, quantumState="ghz"
    )
    constraints = Constraints(
        requested_inputs={1: FloatType(bit_size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    strategy = EncodeValueEnricherStrategy()
    with pytest.raises(
        NodeUnsupportedException,
        match=r"^Node 'PrepareStateNode' is not supported$",
    ):
        await strategy.enrich(node, constraints)


@pytest.mark.asyncio
async def test_enrich_encode_value_two_inputs() -> None:
    node = FrontendEncodeValueNode(
        id="4",
        label=None,
        type="encode",
        encoding="basis",
        bounds=3,
    )
    constraints = Constraints(
        requested_inputs={1: FloatType(bit_size=32), 2: IntType(bit_size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    strategy = EncodeValueEnricherStrategy()
    with pytest.raises(
        ConstraintValidationException,
        match=r"^EncodeValueNode can only have a single input$",
    ):
        await strategy.enrich(node, constraints)


@pytest.mark.asyncio
async def test_enrich_encode_value_quibit_input() -> None:
    node = FrontendEncodeValueNode(
        id="4",
        label=None,
        type="encode",
        encoding="basis",
        bounds=3,
    )
    constraints = Constraints(
        requested_inputs={1: QubitType(1) },
        optimizeDepth=True,
        optimizeWidth=True,
    )

    strategy = EncodeValueEnricherStrategy()
    with pytest.raises(
        ConstraintValidationException,
        match=r"^EncodeValueNode only supports classical types$",
    ):
       await strategy.enrich(node, constraints)


@pytest.mark.asyncio
async def test_enrich_encode_value_node_not_in_db() -> None:
    node = FrontendEncodeValueNode(
        id="4",
        label=None,
        type="encode",
        encoding="basis",
        bounds=3,
    )
    constraints = Constraints(
        requested_inputs={1: FloatType(bit_size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    strategy = EncodeValueEnricherStrategy()
    with pytest.raises(
        NodeUnsupportedException,
        match=r"^Node 'EncodeValueNode' is not supported$",
    ):
        await strategy.enrich(node, constraints)

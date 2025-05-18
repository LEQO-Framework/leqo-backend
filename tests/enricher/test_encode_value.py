from collections.abc import Iterable

import pytest
from sqlalchemy.orm import Session

from app.enricher import (
    Constraints,
    ConstraintValidationException,
    EnrichmentResult,
    InputValidationException,
)
from app.enricher.encode_value import EncodeValueEnricherStrategy
from app.enricher.models import (
    EncodeValueNode,
    EncodingType,
    Input,
    InputType,
    NodeType,
)
from app.model.CompileRequest import EncodeValueNode as FrontendEncodeValueNode
from app.model.CompileRequest import PrepareStateNode as FrontendPrepareStateNode
from app.model.data_types import BitType, BoolType, FloatType, IntType, QubitType


@pytest.fixture(autouse=True)
def setup_database_data(session: Session) -> None:
    node1 = EncodeValueNode(
        type=NodeType.ENCODE,
        depth=1,
        width=1,
        implementation="amplitude_impl",
        encoding=EncodingType.AMPLITUDE,
        bounds=2,
        inputs=[Input(index=0, type=InputType.FloatType, size=32)],
    )
    node2 = EncodeValueNode(
        type=NodeType.ENCODE,
        depth=2,
        width=2,
        implementation="angle_impl",
        encoding=EncodingType.ANGLE,
        bounds=1,
        inputs=[Input(index=0, type=InputType.IntType, size=32)],
    )
    node3 = EncodeValueNode(
        type=NodeType.ENCODE,
        depth=3,
        width=3,
        implementation="matrix_impl",
        encoding=EncodingType.MATRIX,
        bounds=6,
        inputs=[Input(index=0, type=InputType.BitType, size=32)],
    )
    node4 = EncodeValueNode(
        type=NodeType.ENCODE,
        depth=4,
        width=4,
        implementation="schmidt_impl",
        encoding=EncodingType.SCHMIDT,
        bounds=8,
        inputs=[Input(index=0, type=InputType.BoolType, size=1)],
    )

    session.add_all([node1, node2, node3, node4])
    session.commit()
    session.close()


def assert_enrichment(
    enrichment_result: Iterable[EnrichmentResult],
    expected_implementation: str,
    expected_width: int,
    expected_depth: int,
):
    for result in enrichment_result:
        assert result.enriched_node.implementation == expected_implementation
        assert result.meta_data.width == expected_width
        assert result.meta_data.depth == expected_depth


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
        requested_inputs={0: FloatType(bit_size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await EncodeValueEnricherStrategy().enrich(node, constraints)
    assert_enrichment(result, "amplitude_impl", 1, 1)


@pytest.mark.asyncio
async def test_enrich_angle_encode_value() -> None:
    node = FrontendEncodeValueNode(
        id="1",
        label=None,
        type="encode",
        encoding="angle",
        bounds=1,
    )
    constraints = Constraints(
        requested_inputs={0: IntType(bit_size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await EncodeValueEnricherStrategy().enrich(node, constraints)
    assert_enrichment(result, "angle_impl", 2, 2)


@pytest.mark.asyncio
async def test_enrich_matrix_encode_value() -> None:
    node = FrontendEncodeValueNode(
        id="1",
        label=None,
        type="encode",
        encoding="matrix",
        bounds=6,
    )
    constraints = Constraints(
        requested_inputs={0: BitType(bit_size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await EncodeValueEnricherStrategy().enrich(node, constraints)
    assert_enrichment(result, "matrix_impl", 3, 3)


@pytest.mark.asyncio
async def test_enrich_schmidt_encode_value() -> None:
    node = FrontendEncodeValueNode(
        id="1",
        label=None,
        type="encode",
        encoding="schmidt",
        bounds=8,
    )
    constraints = Constraints(
        requested_inputs={0: BoolType()},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await EncodeValueEnricherStrategy().enrich(node, constraints)
    assert_enrichment(result, "schmidt_impl", 4, 4)


@pytest.mark.asyncio
async def test_enrich_custom_encode_value() -> None:
    node = FrontendEncodeValueNode(
        id="1",
        label=None,
        type="encode",
        encoding="custom",
        bounds=8,
    )
    constraints = Constraints(
        requested_inputs={0: FloatType(bit_size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    with pytest.raises(
        InputValidationException,
        match=r"^Custom encoding or bounds below 0 are not supported$",
    ):
        await EncodeValueEnricherStrategy().enrich(node, constraints)


@pytest.mark.asyncio
async def test_enrich_unknown_node() -> None:
    node = FrontendPrepareStateNode(
        id="1", label=None, type="prepare", quantumState="ghz", size=3
    )
    constraints = Constraints(
        requested_inputs={0: FloatType(bit_size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await EncodeValueEnricherStrategy().enrich(node, constraints)

    assert result == []


@pytest.mark.asyncio
async def test_enrich_encode_value_two_inputs() -> None:
    node = FrontendEncodeValueNode(
        id="1",
        label=None,
        type="encode",
        encoding="basis",
        bounds=3,
    )
    constraints = Constraints(
        requested_inputs={0: FloatType(bit_size=32), 1: IntType(bit_size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    with pytest.raises(
        ConstraintValidationException,
        match=r"^EncodeValueNode can only have a single input$",
    ):
        await EncodeValueEnricherStrategy().enrich(node, constraints)


@pytest.mark.asyncio
async def test_enrich_encode_value_quibit_input() -> None:
    node = FrontendEncodeValueNode(
        id="1",
        label=None,
        type="encode",
        encoding="basis",
        bounds=3,
    )
    constraints = Constraints(
        requested_inputs={0: QubitType(reg_size=1)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    with pytest.raises(
        ConstraintValidationException,
        match=r"^EncodeValueNode only supports classical types$",
    ):
        await EncodeValueEnricherStrategy().enrich(node, constraints)


@pytest.mark.asyncio
async def test_enrich_encode_value_node_not_in_db() -> None:
    node = FrontendEncodeValueNode(
        id="1",
        label=None,
        type="encode",
        encoding="basis",
        bounds=3,
    )
    constraints = Constraints(
        requested_inputs={0: IntType(bit_size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    with pytest.raises(
        RuntimeError,
        match=r"^No results found in the database$",
    ):
        await EncodeValueEnricherStrategy().enrich(node, constraints)

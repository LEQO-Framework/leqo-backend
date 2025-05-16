import pytest
from sqlalchemy.orm import Session

from app.enricher import (
    Constraints,
    ConstraintValidationException,
    InputValidationException,
    NodeUnsupportedException,
)
from app.enricher.encode_value import EncodeValueEnricherStrategy
from app.enricher.models import (
    EncodeValueNode,
    EncodingType,
    InputType,
    NodeType,
)
from app.model.CompileRequest import EncodeValueNode as FrontendEncodeValueNode
from app.model.CompileRequest import PrepareStateNode as FrontendPrepareStateNode
from app.model.data_types import BitType, BoolType, FloatType, IntType, QubitType


@pytest.fixture(autouse=True)
def setup_database_data(session: Session) -> None:
    """
    Set up the database with test data for the EncodeValueNode.
    """
    node1 = EncodeValueNode(
        type=NodeType.ENCODE,
        depth=1,
        width=1,
        implementation="amplitude_impl",
        inputs=[{"index": 0, "type": InputType.FloatType.value, "size": 32}],
        encoding=EncodingType.AMPLITUDE,
        bounds=2,
    )
    node2 = EncodeValueNode(
        type=NodeType.ENCODE,
        depth=2,
        width=2,
        implementation="angle_impl",
        inputs=[{"index": 0, "type": InputType.IntType.value, "size": 32}],
        encoding=EncodingType.ANGLE,
        bounds=1,
    )
    node3 = EncodeValueNode(
        type=NodeType.ENCODE,
        depth=3,
        width=3,
        implementation="matrix_impl",
        inputs=[{"index": 0, "type": InputType.BitType.value, "size": 32}],
        encoding=EncodingType.MATRIX,
        bounds=6,
    )
    node4 = EncodeValueNode(
        type=NodeType.ENCODE,
        depth=4,
        width=4,
        implementation="schimdt_impl",
        inputs=[{"index": 0, "type": InputType.BoolType.value, "size": None}],
        encoding=EncodingType.SCHMIDT,
        bounds=8,
    )

    session.add_all([node1, node2, node3, node4])
    session.commit()
    session.close()


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

    assert result is not None
    assert result.enriched_node.implementation == "amplitude_impl"
    assert result.meta_data.width == 1
    assert result.meta_data.depth == 1


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

    assert result is not None
    assert result.enriched_node.implementation == "angle_impl"
    assert result.meta_data.width == 2  # noqa: PLR2004
    assert result.meta_data.depth == 2  # noqa: PLR2004


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

    assert result is not None
    assert result.enriched_node.implementation == "matrix_impl"
    assert result.meta_data.width == 3  # noqa: PLR2004
    assert result.meta_data.depth == 3  # noqa: PLR2004


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
        requested_inputs={0: BoolType()},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await EncodeValueEnricherStrategy().enrich(node, constraints)

    assert result is not None
    assert result.enriched_node.implementation == "schmidt_impl"
    assert result.meta_data.width == 4  # noqa: PLR2004
    assert result.meta_data.depth == 4  # noqa: PLR2004


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
        match=r"^Custom encoding or bounds below 1 are not supported$",
    ):
        await EncodeValueEnricherStrategy().enrich(node, constraints)


@pytest.mark.asyncio
async def test_enrich_unknown_node() -> None:
    node = FrontendPrepareStateNode(
        id="1", label=None, type="prepare", quantumState="ghz"
    )
    constraints = Constraints(
        requested_inputs={0: FloatType(bit_size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    with pytest.raises(
        NodeUnsupportedException,
        match=r"^Node 'PrepareStateNode' is not supported$",
    ):
        await EncodeValueEnricherStrategy().enrich(node, constraints)


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

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.enricher import Constraints
from app.enricher.encode_value import EncodeValueEnricherStrategy
from app.enricher.exceptions import EncodingNotSupported
from app.enricher.models import (
    EncodeValueNode,
    EncodingType,
    Input,
    InputType,
    NodeType,
)
from app.model.CompileRequest import EncodeValueNode as FrontendEncodeValueNode
from app.model.CompileRequest import PrepareStateNode as FrontendPrepareStateNode
from app.model.CompileRequest import SingleInsertMetaData
from app.model.data_types import BitType, BoolType, FloatType, IntType, QubitType
from app.model.exceptions import InputCountMismatch, InputTypeMismatch
from tests.enricher.utils import assert_enrichments
from app.openqasm3.printer import leqo_dumps


@pytest_asyncio.fixture(autouse=True)
async def setup_database_data(session: AsyncSession) -> None:
    node1 = EncodeValueNode(
        type=NodeType.ENCODE,
        depth=1,
        width=1,
        implementation="amplitude_impl",
        encoding=EncodingType.AMPLITUDE,
        bounds=1,
        inputs=[Input(index=0, type=InputType.FloatType, size=32)],
    )
    node2 = EncodeValueNode(
        type=NodeType.ENCODE,
        depth=2,
        width=2,
        implementation="angle_impl",
        encoding=EncodingType.ANGLE,
        bounds=0,
        inputs=[Input(index=0, type=InputType.IntType, size=32)],
    )
    node3 = EncodeValueNode(
        type=NodeType.ENCODE,
        depth=3,
        width=3,
        implementation="matrix_impl",
        encoding=EncodingType.MATRIX,
        bounds=1,
        inputs=[Input(index=0, type=InputType.BitType, size=32)],
    )
    node4 = EncodeValueNode(
        type=NodeType.ENCODE,
        depth=4,
        width=4,
        implementation="schmidt_impl",
        encoding=EncodingType.SCHMIDT,
        bounds=1,
        inputs=[Input(index=0, type=InputType.BoolType, size=1)],
    )

    session.add_all([node1, node2, node3, node4])
    await session.commit()


@pytest.mark.asyncio
async def test_insert_enrichtment(engine: AsyncEngine) -> None:
    node = FrontendEncodeValueNode(
        id="1",
        label=None,
        type="encode",
        encoding="basis",
        bounds=1,
    )

    result = await EncodeValueEnricherStrategy(engine).insert_enrichment(
        node=node,
        implementation="basis_impl",
        requested_inputs={0: FloatType(size=32)},
        meta_data=SingleInsertMetaData(width=1, depth=1),
    )

    assert result is True
    async with AsyncSession(engine) as session:
        db_result = await session.execute(
            select(EncodeValueNode).where(
                EncodeValueNode.implementation == "basis_impl",
                EncodeValueNode.type == NodeType.ENCODE,
                EncodeValueNode.encoding == EncodingType.BASIS,
                EncodeValueNode.depth == 1,
                EncodeValueNode.width == 1,
            )
        )
        node_in_db = db_result.scalar_one_or_none()
        assert node_in_db is not None


@pytest.mark.asyncio
async def test_enrich_amplitude_encode_value(engine: AsyncEngine) -> None:
    node = FrontendEncodeValueNode(
        id="1",
        label=None,
        type="encode",
        encoding="amplitude",
        bounds=1,
    )
    constraints = Constraints(
        requested_inputs={0: FloatType(size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await EncodeValueEnricherStrategy(engine).enrich(node, constraints)
    assert_enrichments(result, "amplitude_impl", 1, 1)


@pytest.mark.asyncio
async def test_enrich_angle_encode_value(engine: AsyncEngine) -> None:
    node = FrontendEncodeValueNode(
        id="1",
        label=None,
        type="encode",
        encoding="angle",
        bounds=0,
    )
    constraints = Constraints(
        requested_inputs={0: IntType(size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await EncodeValueEnricherStrategy(engine).enrich(node, constraints)
    assert_enrichments(result, "angle_impl", 2, 2)


@pytest.mark.asyncio
async def test_enrich_matrix_encode_value(engine: AsyncEngine) -> None:
    node = FrontendEncodeValueNode(
        id="1",
        label=None,
        type="encode",
        encoding="matrix",
        bounds=1,
    )
    constraints = Constraints(
        requested_inputs={0: BitType(size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await EncodeValueEnricherStrategy(engine).enrich(node, constraints)
    assert_enrichments(result, "matrix_impl", 3, 3)


@pytest.mark.asyncio
async def test_enrich_schmidt_encode_value(engine: AsyncEngine) -> None:
    node = FrontendEncodeValueNode(
        id="1",
        label=None,
        type="encode",
        encoding="schmidt",
        bounds=1,
    )
    constraints = Constraints(
        requested_inputs={0: BoolType()},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await EncodeValueEnricherStrategy(engine).enrich(node, constraints)
    assert_enrichments(result, "schmidt_impl", 4, 4)


@pytest.mark.asyncio
async def test_enrich_custom_encode_value(engine: AsyncEngine) -> None:
    node = FrontendEncodeValueNode(
        id="1",
        label=None,
        type="encode",
        encoding="custom",
        bounds=1,
    )
    constraints = Constraints(
        requested_inputs={0: FloatType(size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    with pytest.raises(
        EncodingNotSupported,
        match=r"^Encoding 'custom' not supported$",
    ):
        await EncodeValueEnricherStrategy(engine).enrich(node, constraints)


@pytest.mark.asyncio
async def test_enrich_unknown_node(engine: AsyncEngine) -> None:
    node = FrontendPrepareStateNode(
        id="1", label=None, type="prepare", quantumState="ghz", size=3
    )
    constraints = Constraints(
        requested_inputs={0: FloatType(size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await EncodeValueEnricherStrategy(engine).enrich(node, constraints)

    assert result == []


@pytest.mark.asyncio
async def test_enrich_encode_value_two_inputs(engine: AsyncEngine) -> None:
    node = FrontendEncodeValueNode(
        id="1",
        label=None,
        type="encode",
        encoding="basis",
        bounds=0,
    )
    constraints = Constraints(
        requested_inputs={0: FloatType(size=32), 1: IntType(size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    with pytest.raises(
        InputCountMismatch,
        match=r"^Node should have 1 inputs. Got 2.$",
    ):
        await EncodeValueEnricherStrategy(engine).enrich(node, constraints)


@pytest.mark.asyncio
async def test_enrich_encode_value_quibit_input(engine: AsyncEngine) -> None:
    node = FrontendEncodeValueNode(
        id="1",
        label=None,
        type="encode",
        encoding="basis",
        bounds=1,
    )
    constraints = Constraints(
        requested_inputs={0: QubitType(size=1)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    with pytest.raises(
        InputTypeMismatch,
        match=r"^Expected type 'classical' for input 0. Got 'QubitType\(size=1\)'.$",
    ):
        await EncodeValueEnricherStrategy(engine).enrich(node, constraints)


@pytest.mark.asyncio
async def test_enrich_encode_value_node_not_in_db(engine: AsyncEngine) -> None:
    node = FrontendEncodeValueNode(
        id="1",
        label=None,
        type="encode",
        encoding="basis",
        bounds=1,
    )
    constraints = Constraints(
        requested_inputs={0: IntType(size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    results = list(await EncodeValueEnricherStrategy(engine).enrich(node, constraints))

    assert len(results) == 1

    result = results[0]
    implementation = result.enriched_node.implementation
    implementation_str = (
        implementation
        if isinstance(implementation, str)
        else leqo_dumps(implementation)
    )

    assert '@leqo.input 0' in implementation_str
    assert 'int[32] value;' in implementation_str
    assert 'qubit[32] encoded;' in implementation_str
    assert implementation_str.count('if') == 32
    assert 'x encoded[0];' in implementation_str
    assert 'x encoded[31];' in implementation_str
    assert '@leqo.output 0' in implementation_str
    assert 'let out = encoded;' in implementation_str
    assert result.meta_data.width == 32
    assert result.meta_data.depth == 32

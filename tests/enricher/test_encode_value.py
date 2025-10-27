import pytest
import pytest_asyncio
from sqlalchemy import delete, select
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
from app.model.data_types import (
    ArrayType,
    BitType,
    BoolType,
    FloatType,
    IntType,
    QubitType,
)
from app.model.exceptions import InputCountMismatch, InputTypeMismatch
from app.openqasm3.printer import leqo_dumps
from tests.enricher.utils import assert_enrichments

ENCODE_REGISTER_SIZE = 32
LITERAL_ENCODE_DEPTH = 2


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
async def test_enrich_encode_value_bit_literal(engine: AsyncEngine) -> None:
    node = FrontendEncodeValueNode(
        id="1",
        label=None,
        type="encode",
        encoding="basis",
        bounds=0,
    )
    constraints = Constraints(
        requested_inputs={0: BitType(size=None)},
        requested_input_values={0: 1},
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

    assert "qubit[1] encoded;" in implementation_str
    assert implementation_str.count("x encoded[0];") == 1
    assert "@leqo.output 0" in implementation_str
    assert result.meta_data.width == 1
    assert result.meta_data.depth == 1


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

    assert "@leqo.input 0" in implementation_str
    assert "int[32] value;" in implementation_str
    assert "qubit[32] encoded;" in implementation_str
    assert implementation_str.count("if") == ENCODE_REGISTER_SIZE
    assert "x encoded[0];" in implementation_str
    assert "x encoded[31];" in implementation_str
    assert "@leqo.output 0" in implementation_str
    assert "let out = encoded;" in implementation_str
    assert result.meta_data.width == ENCODE_REGISTER_SIZE
    assert result.meta_data.depth == ENCODE_REGISTER_SIZE


@pytest.mark.asyncio
async def test_enrich_encode_value_node_not_in_db_with_literal_value(
    engine: AsyncEngine,
) -> None:
    expected_width = 3
    node = FrontendEncodeValueNode(
        id="1",
        label=None,
        type="encode",
        encoding="basis",
        bounds=1,
    )
    constraints = Constraints(
        requested_inputs={0: IntType(size=expected_width)},
        requested_input_values={0: 5},
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

    assert "@leqo.input 0" not in implementation_str
    assert "int[32] value;" not in implementation_str
    assert "if" not in implementation_str
    assert f"qubit[{expected_width}] encoded;" in implementation_str
    assert implementation_str.count("x encoded[0];") == 1
    assert implementation_str.count("x encoded[2];") == 1
    assert "x encoded[1];" not in implementation_str
    assert "@leqo.output 0" in implementation_str
    assert "let out = encoded;" in implementation_str
    assert result.meta_data.width == expected_width
    assert result.meta_data.depth == LITERAL_ENCODE_DEPTH


@pytest.mark.asyncio
async def test_enrich_angle_encode_value_node_not_in_db(engine: AsyncEngine) -> None:
    async with AsyncSession(engine) as session:
        await session.execute(
            delete(EncodeValueNode).where(
                EncodeValueNode.encoding == EncodingType.ANGLE
            )
        )
        await session.commit()

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

    results = list(await EncodeValueEnricherStrategy(engine).enrich(node, constraints))

    assert len(results) == 1

    result = results[0]
    implementation = result.enriched_node.implementation
    implementation_str = (
        implementation
        if isinstance(implementation, str)
        else leqo_dumps(implementation)
    )

    assert "@leqo.input 0" in implementation_str
    assert "int[32] value;" in implementation_str
    assert "qubit[32] encoded;" in implementation_str
    assert implementation_str.count("ry(3.141592653589793)") == ENCODE_REGISTER_SIZE
    assert "@leqo.output 0" in implementation_str
    assert "let out = encoded;" in implementation_str
    assert result.meta_data.width == ENCODE_REGISTER_SIZE
    assert result.meta_data.depth == ENCODE_REGISTER_SIZE


@pytest.mark.asyncio
async def test_enrich_encode_value_array_literal(engine: AsyncEngine) -> None:
    node = FrontendEncodeValueNode(
        id="1",
        label=None,
        type="encode",
        encoding="basis",
        bounds=1,
    )
    element_size = 3
    array_type = ArrayType.with_size(element_size, 2)
    array_values = [1, 6]
    constraints = Constraints(
        requested_inputs={0: array_type},
        requested_input_values={0: array_values},
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

    assert "@leqo.input 0" not in implementation_str
    assert "array[int" not in implementation_str
    total_size = array_type.size
    assert f"qubit[{total_size}] encoded;" in implementation_str
    for index in (0, 4, 5):
        assert f"x encoded[{index}];" in implementation_str
    expected_depth = sum(
        (value & ((1 << element_size) - 1)).bit_count() for value in array_values
    )
    assert result.meta_data.width == total_size
    assert result.meta_data.depth == expected_depth


@pytest.mark.asyncio
async def test_enrich_encode_value_array_input(engine: AsyncEngine) -> None:
    node = FrontendEncodeValueNode(
        id="1",
        label=None,
        type="encode",
        encoding="basis",
        bounds=1,
    )
    array_type = ArrayType.with_size(3, 2)
    constraints = Constraints(
        requested_inputs={0: array_type},
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

    assert "@leqo.input 0" in implementation_str
    assert "array[int[3], 2] value;" in implementation_str
    assert f"qubit[{array_type.size}] encoded;" in implementation_str
    assert implementation_str.count("if") == array_type.size
    assert "@leqo.output 0" in implementation_str
    assert result.meta_data.width == array_type.size
    assert result.meta_data.depth == array_type.size


@pytest.mark.asyncio
async def test_enrich_angle_encode_value_array_literal(engine: AsyncEngine) -> None:
    node = FrontendEncodeValueNode(
        id="1",
        label=None,
        type="encode",
        encoding="angle",
        bounds=0,
    )
    array_type = ArrayType.with_size(3, 2)
    array_values = [1, 6]
    constraints = Constraints(
        requested_inputs={0: array_type},
        requested_input_values={0: array_values},
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

    assert "@leqo.input 0" not in implementation_str
    assert "array[int[3], 2] value;" not in implementation_str
    assert "if" not in implementation_str
    assert f"qubit[{array_type.size}] encoded;" in implementation_str
    expected_depth = sum(
        (value & ((1 << array_type.element_type.size) - 1)).bit_count()
        for value in array_values
    )
    assert implementation_str.count("ry(3.141592653589793)") == expected_depth
    assert "@leqo.output 0" in implementation_str
    assert result.meta_data.width == array_type.size
    assert result.meta_data.depth == expected_depth


@pytest.mark.asyncio
async def test_enrich_angle_encode_value_array_input(engine: AsyncEngine) -> None:
    node = FrontendEncodeValueNode(
        id="1",
        label=None,
        type="encode",
        encoding="angle",
        bounds=0,
    )
    array_type = ArrayType.with_size(3, 2)
    constraints = Constraints(
        requested_inputs={0: array_type},
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

    assert "@leqo.input 0" in implementation_str
    assert "array[int[3], 2] value;" in implementation_str
    assert f"qubit[{array_type.size}] encoded;" in implementation_str
    assert implementation_str.count("if") == array_type.size
    assert implementation_str.count("ry(3.141592653589793)") == array_type.size
    assert "@leqo.output 0" in implementation_str
    assert result.meta_data.width == array_type.size
    assert result.meta_data.depth == array_type.size

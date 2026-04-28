import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.enricher import Constraints
from app.enricher.encode_value import EncodeValueEnricherStrategy
from app.enricher.models import EncodeValueNode, EncodingType
from app.model.CompileRequest import EncodeValueNode as FrontendEncodeValueNode
from app.model.data_types import ArrayType
from app.openqasm3.printer import leqo_dumps


@pytest_asyncio.fixture(autouse=True)
async def remove_matrix_entries(session: AsyncSession) -> None:
    await session.execute(
        delete(EncodeValueNode).where(EncodeValueNode.encoding == EncodingType.MATRIX)
    )
    await session.commit()


@pytest.mark.asyncio
async def test_enrich_matrix_encode_value_array_literal(engine: AsyncEngine) -> None:
    node = FrontendEncodeValueNode(
        id="1",
        label=None,
        type="encode",
        encoding="matrix",
        bounds=1,
    )
    array_type = ArrayType.with_size(32, 4)
    matrix_values = [0, 1, 1, 0]  # 2x2 X matrix

    constraints = Constraints(
        requested_inputs={0: array_type},
        requested_input_values={0: matrix_values},
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
    assert "qubit[1] encoded;" in implementation_str
    assert "@leqo.output 0" in implementation_str
    assert "let out = encoded;" in implementation_str
    assert result.meta_data.width == 1
    assert result.meta_data.depth is not None


@pytest.mark.asyncio
async def test_enrich_matrix_encode_value_rejects_non_unitary(
    engine: AsyncEngine,
) -> None:
    node = FrontendEncodeValueNode(
        id="1",
        label=None,
        type="encode",
        encoding="matrix",
        bounds=1,
    )
    array_type = ArrayType.with_size(32, 4)
    matrix_values = [1, 1, 0, 1]

    constraints = Constraints(
        requested_inputs={0: array_type},
        requested_input_values={0: matrix_values},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    with pytest.raises(
        RuntimeError,
        match=r"^Matrix encoding v1 expects a unitary matrix\.$",
    ):
        await EncodeValueEnricherStrategy(engine).enrich(node, constraints)


@pytest.mark.asyncio
async def test_enrich_matrix_encode_value_rejects_non_square_length(
    engine: AsyncEngine,
) -> None:
    node = FrontendEncodeValueNode(
        id="1",
        label=None,
        type="encode",
        encoding="matrix",
        bounds=1,
    )
    array_type = ArrayType.with_size(32, 3)
    matrix_values = [1, 0, 1]

    constraints = Constraints(
        requested_inputs={0: array_type},
        requested_input_values={0: matrix_values},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    with pytest.raises(
        RuntimeError,
        match=r"^Matrix encoding expects a flat square matrix \(length must be n\^2\)\.$",
    ):
        await EncodeValueEnricherStrategy(engine).enrich(node, constraints)

from collections.abc import Iterable

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.enricher import (
    Constraints,
    ConstraintValidationException,
    EnrichmentResult,
    InputValidationException,
)
from app.enricher.models import NodeType, PrepareStateNode, QuantumStateType
from app.enricher.prepare_state import PrepareStateEnricherStrategy
from app.model.CompileRequest import EncodeValueNode as FrontendEncodeValueNode
from app.model.CompileRequest import PrepareStateNode as FrontendPrepareStateNode
from app.model.data_types import FloatType


@pytest_asyncio.fixture(autouse=True)
async def setup_database_data(session: AsyncSession) -> None:
    """
    Set up the database with test data for the PrepareStateNode.
    """
    node1 = PrepareStateNode(
        type=NodeType.PREPARE,
        depth=1,
        width=1,
        implementation="phi_plus_impl",
        inputs=[],
        quantum_state=QuantumStateType.PHI_PLUS,
        size=1,
    )
    node2 = PrepareStateNode(
        type=NodeType.PREPARE,
        depth=2,
        width=2,
        implementation="psi_plus_impl",
        inputs=[],
        quantum_state=QuantumStateType.PSI_PLUS,
        size=3,
    )
    node3 = PrepareStateNode(
        type=NodeType.PREPARE,
        depth=3,
        width=3,
        implementation="gzh_impl",
        inputs=[],
        quantum_state=QuantumStateType.GHZ,
        size=6,
    )
    node4 = PrepareStateNode(
        type=NodeType.PREPARE,
        depth=4,
        width=4,
        implementation="superposition_impl",
        inputs=[],
        quantum_state=QuantumStateType.UNIFORM,
        size=4,
    )
    node5 = PrepareStateNode(
        type=NodeType.PREPARE,
        depth=6,
        width=9,
        implementation="w_impl",
        inputs=[],
        quantum_state=QuantumStateType.W,
        size=9,
    )

    session.add_all([node1, node2, node3, node4, node5])
    await session.commit()


def assert_enrichment(
    enrichment_result: Iterable[EnrichmentResult],
    expected_implementation: str,
    expected_width: int,
    expected_depth: int,
) -> None:
    for result in enrichment_result:
        assert result.enriched_node.implementation == expected_implementation
        assert result.meta_data.width == expected_width
        assert result.meta_data.depth == expected_depth


@pytest.mark.asyncio
async def test_enrich_phi_plus_prepare_state() -> None:
    node = FrontendPrepareStateNode(
        id="1", label=None, type="prepare", quantumState="ϕ+", size=1
    )
    constraints = Constraints(
        requested_inputs={},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await PrepareStateEnricherStrategy().enrich(node, constraints)
    assert_enrichment(result, "phi_plus_impl", 1, 1)


@pytest.mark.asyncio
async def test_enrich_psi_plus_prepare_state() -> None:
    node = FrontendPrepareStateNode(
        id="1", label=None, type="prepare", quantumState="ψ+", size=3
    )
    constraints = Constraints(
        requested_inputs={},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await PrepareStateEnricherStrategy().enrich(node, constraints)
    assert_enrichment(result, "psi_plus_impl", 2, 2)


@pytest.mark.asyncio
async def test_enrich_gzh_prepare_state() -> None:
    node = FrontendPrepareStateNode(
        id="3", label=None, type="prepare", quantumState="ghz", size=6
    )
    constraints = Constraints(
        requested_inputs={},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await PrepareStateEnricherStrategy().enrich(node, constraints)
    assert_enrichment(result, "gzh_impl", 3, 3)


@pytest.mark.asyncio
async def test_enrich_superposition_prepare_state() -> None:
    node = FrontendPrepareStateNode(
        id="4", label=None, type="prepare", quantumState="uniform", size=4
    )
    constraints = Constraints(
        requested_inputs={},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await PrepareStateEnricherStrategy().enrich(node, constraints)
    assert_enrichment(result, "superposition_impl", 4, 4)


@pytest.mark.asyncio
async def test_enrich_w_prepare_state() -> None:
    node = FrontendPrepareStateNode(
        id="5", label=None, type="prepare", quantumState="w", size=9
    )
    constraints = Constraints(
        requested_inputs={},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await PrepareStateEnricherStrategy().enrich(node, constraints)
    assert_enrichment(result, "w_impl", 9, 6)


@pytest.mark.asyncio
async def test_enrich_custom_prepare_state() -> None:
    node = FrontendPrepareStateNode(
        id="1", label=None, type="prepare", quantumState="custom", size=3
    )
    constraints = Constraints(
        requested_inputs={},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    with pytest.raises(
        InputValidationException,
        match=r"^Custom prepare state or size below 1 are not supported$",
    ):
        await PrepareStateEnricherStrategy().enrich(node, constraints)


@pytest.mark.asyncio
async def test_enrich_unknown_node() -> None:
    node = FrontendEncodeValueNode(
        id="1", label=None, type="encode", encoding="angle", bounds=0
    )
    constraints = Constraints(
        requested_inputs={0: FloatType(bit_size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await PrepareStateEnricherStrategy().enrich(node, constraints)

    assert result == []


@pytest.mark.asyncio
async def test_enrich_prepare_state_one_inputs() -> None:
    node = FrontendPrepareStateNode(
        id="1", label=None, type="prepare", quantumState="ghz", size=4
    )
    constraints = Constraints(
        requested_inputs={0: FloatType(bit_size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    with pytest.raises(
        ConstraintValidationException,
        match=r"^PrepareStateNode can't have an input$",
    ):
        await PrepareStateEnricherStrategy().enrich(node, constraints)


@pytest.mark.asyncio
async def test_enrich_prepare_state_node_not_in_db() -> None:
    node = FrontendPrepareStateNode(
        id="1", label=None, type="prepare", quantumState="ϕ-", size=2
    )
    constraints = Constraints(
        requested_inputs={},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    with pytest.raises(
        RuntimeError,
        match=r"^No results found in the database$",
    ):
        await PrepareStateEnricherStrategy().enrich(node, constraints)

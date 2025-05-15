import pytest
from sqlalchemy.orm import Session

from app.enricher import (
    Constraints,
    ConstraintValidationException,
    InputValidationException,
    NodeUnsupportedException,
)
from app.enricher.models import NodeType, PrepareStateNode, QuantumStateType
from app.enricher.prepare_state import PrepareStateEnricherStrategy
from app.model.CompileRequest import EncodeValueNode as FrontendEncodeValueNode
from app.model.CompileRequest import PrepareStateNode as FrontendPrepareStateNode
from app.model.data_types import FloatType


@pytest.fixture(autouse=True)
def setup_database_data(session: Session) -> None:
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
        size=2,
    )
    node2 = PrepareStateNode(
        type=NodeType.PREPARE,
        depth=2,
        width=2,
        implementation="psi_plus_impl",
        inputs=[],
        quantum_state=QuantumStateType.PSI_PLUS,
        size=1,
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
        size=8,
    )
    node5 = PrepareStateNode(
        type=NodeType.PREPARE,
        depth=6,
        width=9,
        implementation="w_impl",
        inputs=[],
        quantum_state=QuantumStateType.W,
        size=3,
    )

    session.add_all([node1, node2, node3, node4, node5])
    session.commit()
    session.close()


@pytest.mark.asyncio
async def test_enrich_phi_plus_prepare_state() -> None:
    node = FrontendPrepareStateNode(
        id="1",
        label=None,
        type="prepare",
        size=2,
        quantumState="ϕ+",
    )
    constraints = Constraints(
        requested_inputs={},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await PrepareStateEnricherStrategy().enrich(node, constraints)

    assert result is not None
    assert result.enriched_node.implementation == "phi_plus_impl"
    assert result.meta_data.width == 1
    assert result.meta_data.depth == 1


@pytest.mark.asyncio
async def test_enrich_psi_plus_prepare_state() -> None:
    node = FrontendPrepareStateNode(
        id="1",
        label=None,
        type="prepare",
        size=1,
        quantumState="ψ+",
    )
    constraints = Constraints(
        requested_inputs={},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await PrepareStateEnricherStrategy().enrich(node, constraints)

    assert result is not None
    assert result.enriched_node.implementation == "psi_plus_impl"
    assert result.meta_data.width == 2  # noqa: PLR2004
    assert result.meta_data.depth == 2  # noqa: PLR2004


@pytest.mark.asyncio
async def test_enrich_gzh_prepare_state() -> None:
    node = FrontendPrepareStateNode(
        id="3",
        label=None,
        type="prepare",
        size=6,
        quantumState="ghz",
    )
    constraints = Constraints(
        requested_inputs={},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await PrepareStateEnricherStrategy().enrich(node, constraints)

    assert result is not None
    assert result.enriched_node.implementation == "gzh_impl"
    assert result.meta_data.width == 3  # noqa: PLR2004
    assert result.meta_data.depth == 3  # noqa: PLR2004


@pytest.mark.asyncio
async def test_enrich_superposition_prepare_state() -> None:
    node = FrontendPrepareStateNode(
        id="4",
        label=None,
        type="prepare",
        size=8,
        quantumState="uniform",
    )
    constraints = Constraints(
        requested_inputs={},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await PrepareStateEnricherStrategy().enrich(node, constraints)

    assert result is not None
    assert result.enriched_node.implementation == "superposition_impl"
    assert result.meta_data.width == 4  # noqa: PLR2004
    assert result.meta_data.depth == 4  # noqa: PLR2004


@pytest.mark.asyncio
async def test_enrich_w_prepare_state() -> None:
    node = FrontendPrepareStateNode(
        id="5",
        label=None,
        type="prepare",
        size=3,
        quantumState="w",
    )
    constraints = Constraints(
        requested_inputs={},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await PrepareStateEnricherStrategy().enrich(node, constraints)

    assert result is not None
    assert result.enriched_node.implementation == "w_impl"
    assert result.meta_data.width == 9  # noqa: PLR2004
    assert result.meta_data.depth == 6  # noqa: PLR2004


@pytest.mark.asyncio
async def test_enrich_custom_prepare_state() -> None:
    node = FrontendPrepareStateNode(
        id="1", label=None, type="prepare", size=5, quantumState="custom"
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
        id="1", label=None, type="encode", encoding="angle", bounds=3
    )
    constraints = Constraints(
        requested_inputs={0: FloatType(bit_size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    with pytest.raises(
        NodeUnsupportedException,
        match=r"^Node 'EncodeValueNode' is not supported$",
    ):
        await PrepareStateEnricherStrategy().enrich(node, constraints)


@pytest.mark.asyncio
async def test_enrich_prepare_state_one_inputs() -> None:
    node = FrontendPrepareStateNode(
        id="1",
        label=None,
        type="prepare",
        size=3,
        quantumState="ghz",
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
        id="1", label=None, type="prepare", size=5, quantumState="ϕ-"
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

import math

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.enricher import Constraints
from app.enricher.exceptions import QuantumStateNotSupported
from app.enricher.models import NodeType, PrepareStateNode, QuantumStateType
from app.enricher.prepare_state import PrepareStateEnricherStrategy
from app.model.CompileRequest import EncodeValueNode as FrontendEncodeValueNode
from app.model.CompileRequest import PrepareStateNode as FrontendPrepareStateNode
from app.model.CompileRequest import SingleInsertMetaData
from app.model.data_types import FloatType
from app.model.exceptions import InputCountMismatch
from app.openqasm3.printer import leqo_dumps
from tests.enricher.utils import assert_enrichments


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

    session.add_all([node1, node2, node3])
    await session.commit()


@pytest.mark.asyncio
async def test_insert_enrichtment(engine: AsyncEngine) -> None:
    node = FrontendPrepareStateNode(
        id="1", label=None, type="prepare", quantumState="ϕ-", size=1
    )

    result = await PrepareStateEnricherStrategy(engine).insert_enrichment(
        node=node,
        implementation="phi_minus_impl",
        requested_inputs={},
        meta_data=SingleInsertMetaData(width=1, depth=1),
    )

    assert result is True
    async with AsyncSession(engine) as session:
        db_result = await session.execute(
            select(PrepareStateNode).where(
                PrepareStateNode.implementation == "phi_minus_impl",
                PrepareStateNode.type == NodeType.PREPARE,
                PrepareStateNode.quantum_state == QuantumStateType.PHI_MINUS,
                PrepareStateNode.size == 1,
                PrepareStateNode.depth == 1,
                PrepareStateNode.width == 1,
            )
        )
        node_in_db = db_result.scalar_one_or_none()
        assert node_in_db is not None


@pytest.mark.asyncio
async def test_enrich_phi_plus_prepare_state(engine: AsyncEngine) -> None:
    node = FrontendPrepareStateNode(
        id="1", label=None, type="prepare", quantumState="ϕ+", size=1
    )
    constraints = Constraints(
        requested_inputs={},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await PrepareStateEnricherStrategy(engine).enrich(node, constraints)
    assert_enrichments(result, "phi_plus_impl", 1, 1)


@pytest.mark.asyncio
async def test_enrich_psi_plus_prepare_state(engine: AsyncEngine) -> None:
    node = FrontendPrepareStateNode(
        id="1", label=None, type="prepare", quantumState="ψ+", size=3
    )
    constraints = Constraints(
        requested_inputs={},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await PrepareStateEnricherStrategy(engine).enrich(node, constraints)
    assert_enrichments(result, "psi_plus_impl", 2, 2)


@pytest.mark.asyncio
async def test_enrich_gzh_prepare_state(engine: AsyncEngine) -> None:
    node = FrontendPrepareStateNode(
        id="3", label=None, type="prepare", quantumState="ghz", size=6
    )
    constraints = Constraints(
        requested_inputs={},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await PrepareStateEnricherStrategy(engine).enrich(node, constraints)
    assert_enrichments(result, "gzh_impl", 3, 3)


@pytest.mark.asyncio
async def test_enrich_superposition_prepare_state(engine: AsyncEngine) -> None:
    node = FrontendPrepareStateNode(
        id="4", label=None, type="prepare", quantumState="uniform", size=4
    )
    constraints = Constraints(
        requested_inputs={},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    results = list(await PrepareStateEnricherStrategy(engine).enrich(node, constraints))
    assert len(results) == 1

    implementation = results[0].enriched_node.implementation
    implementation_str = (
        implementation
        if isinstance(implementation, str)
        else leqo_dumps(implementation)
    )

    assert "qubit[4] q;" in implementation_str
    assert "h q;" in implementation_str
    assert "@leqo.output 0" in implementation_str


@pytest.mark.asyncio
async def test_enrich_w_prepare_state(engine: AsyncEngine) -> None:
    """
    Tests that a W-State node generates the correct sequential
    controlled-RY and CNOT ladder for amplitude distribution.
    """
    node = FrontendPrepareStateNode(
        id="w-state-node-1",
        label="Prepare State",
        type="prepare",
        quantumState="w",
        size=3,
    )

    constraints = Constraints(
        requested_inputs={},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    results = list(await PrepareStateEnricherStrategy(engine).enrich(node, constraints))
    assert len(results) == 1

    result = results[0]
    implementation = result.enriched_node.implementation

    implementation_str = (
        implementation
        if isinstance(implementation, str)
        else leqo_dumps(implementation)
    )

    assert "qubit[3] q;" in implementation_str
    assert "x q[0];" in implementation_str

    theta_0 = 2 * math.asin(math.sqrt(2 / 3))
    theta_1 = 2 * math.asin(math.sqrt(1 / 2))

    assert f"cry({theta_0}) q[0], q[1];" in implementation_str
    assert "cx q[1], q[0];" in implementation_str
    assert f"cry({theta_1}) q[1], q[2];" in implementation_str
    assert "cx q[2], q[1];" in implementation_str

    assert "@leqo.output 0" in implementation_str
    assert "let out = q;" in implementation_str

    expected_width = 3
    expected_depth = 6
    assert result.meta_data.width == expected_width
    assert result.meta_data.depth == expected_depth


@pytest.mark.asyncio
async def test_enrich_custom_prepare_state(engine: AsyncEngine) -> None:
    node = FrontendPrepareStateNode(
        id="1", label=None, type="prepare", quantumState="custom", size=3
    )
    constraints = Constraints(
        requested_inputs={},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    with pytest.raises(
        QuantumStateNotSupported,
        match=r"^Quantum state 'custom' not supported$",
    ):
        await PrepareStateEnricherStrategy(engine).enrich(node, constraints)


@pytest.mark.asyncio
async def test_enrich_unknown_node(engine: AsyncEngine) -> None:
    node = FrontendEncodeValueNode(
        id="1", label=None, type="encode", encoding="angle", bounds=0
    )
    constraints = Constraints(
        requested_inputs={0: FloatType(size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await PrepareStateEnricherStrategy(engine).enrich(node, constraints)

    assert result == []


@pytest.mark.asyncio
async def test_enrich_prepare_state_one_inputs(engine: AsyncEngine) -> None:
    node = FrontendPrepareStateNode(
        id="1", label=None, type="prepare", quantumState="ghz", size=4
    )
    constraints = Constraints(
        requested_inputs={0: FloatType(size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    with pytest.raises(
        InputCountMismatch,
        match=r"^Node should have 0 inputs\. Got 1\.$",
    ):
        await PrepareStateEnricherStrategy(engine).enrich(node, constraints)


@pytest.mark.asyncio
async def test_enrich_prepare_state_node_not_in_db(engine: AsyncEngine) -> None:
    node = FrontendPrepareStateNode(
        id="1", label=None, type="prepare", quantumState="ϕ-", size=2
    )
    constraints = Constraints(
        requested_inputs={},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    assert (await PrepareStateEnricherStrategy(engine).enrich(node, constraints)) == []

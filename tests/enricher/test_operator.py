import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.enricher import Constraints
from app.enricher.models import Input, InputType, NodeType, OperatorNode, OperatorType
from app.enricher.operator import OperatorEnricherStrategy
from app.model.CompileRequest import OperatorNode as FrontendOperatorNode
from app.model.CompileRequest import PrepareStateNode as FrontendPrepareStateNode
from app.model.data_types import FloatType, QubitType
from app.model.exceptions import InputCountMismatch, InputTypeMismatch
from tests.enricher.utils import assert_enrichments


@pytest_asyncio.fixture(autouse=True)
async def setup_database_data(session: AsyncSession) -> None:
    """
    Set up the database with test data for the OperatorNode.
    """

    node1 = OperatorNode(
        type=NodeType.OPERATOR,
        depth=1,
        width=2,
        implementation="addition_impl",
        inputs=[
            Input(index=0, type=InputType.QubitType, size=2),
            Input(index=1, type=InputType.QubitType, size=3),
        ],
        operator=OperatorType.ADD,
    )
    node2 = OperatorNode(
        type=NodeType.OPERATOR,
        depth=2,
        width=2,
        implementation="multiplication_impl",
        inputs=[
            Input(index=0, type=InputType.QubitType, size=1),
            Input(index=1, type=InputType.QubitType, size=4),
        ],
        operator=OperatorType.MUL,
    )
    node3 = OperatorNode(
        type=NodeType.OPERATOR,
        depth=3,
        width=3,
        implementation="or_impl",
        inputs=[
            Input(index=0, type=InputType.QubitType, size=4),
            Input(index=1, type=InputType.QubitType, size=3),
        ],
        operator=OperatorType.OR,
    )
    node4 = OperatorNode(
        type=NodeType.OPERATOR,
        depth=3,
        width=4,
        implementation="greater_than_impl",
        inputs=[
            Input(index=0, type=InputType.QubitType, size=5),
            Input(index=1, type=InputType.QubitType, size=4),
        ],
        operator=OperatorType.GT,
    )
    node5 = OperatorNode(
        type=NodeType.OPERATOR,
        depth=4,
        width=5,
        implementation="minimum_impl",
        inputs=[
            Input(index=0, type=InputType.QubitType, size=5),
            Input(index=1, type=InputType.QubitType, size=6),
        ],
        operator=OperatorType.MIN,
    )

    session.add_all([node1, node2, node3, node4, node5])
    await session.commit()


@pytest.mark.asyncio
async def test_enrich_plus_operator(engine: AsyncEngine) -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="+")
    constraints = Constraints(
        requested_inputs={0: QubitType(size=2), 1: QubitType(size=3)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await OperatorEnricherStrategy(engine).enrich(node, constraints)
    assert_enrichments(result, "addition_impl", 2, 1)


@pytest.mark.asyncio
async def test_enrich_multiplication_operator(engine: AsyncEngine) -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="*")
    constraints = Constraints(
        requested_inputs={0: QubitType(size=1), 1: QubitType(size=4)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await OperatorEnricherStrategy(engine).enrich(node, constraints)
    assert_enrichments(result, "multiplication_impl", 2, 2)


@pytest.mark.asyncio
async def test_enrich_OR_operator(engine: AsyncEngine) -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="|")
    constraints = Constraints(
        requested_inputs={0: QubitType(size=4), 1: QubitType(size=3)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await OperatorEnricherStrategy(engine).enrich(node, constraints)
    assert_enrichments(result, "or_impl", 3, 3)


@pytest.mark.asyncio
async def test_enrich_greater_operator(engine: AsyncEngine) -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator=">")
    constraints = Constraints(
        requested_inputs={0: QubitType(size=5), 1: QubitType(size=4)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await OperatorEnricherStrategy(engine).enrich(node, constraints)
    assert_enrichments(result, "greater_than_impl", 4, 3)


@pytest.mark.asyncio
async def test_enrich_min_operator(engine: AsyncEngine) -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="min")
    constraints = Constraints(
        requested_inputs={0: QubitType(size=5), 1: QubitType(size=6)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await OperatorEnricherStrategy(engine).enrich(node, constraints)
    assert_enrichments(result, "minimum_impl", 5, 4)


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

    result = await OperatorEnricherStrategy(engine).enrich(node, constraints)

    assert result == []


@pytest.mark.asyncio
async def test_enrich_operator_one_inputs(engine: AsyncEngine) -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="!=")
    constraints = Constraints(
        requested_inputs={0: QubitType(size=7)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    with pytest.raises(
        InputCountMismatch,
        match=r"^Node should have 2 inputs\. Got 1\.$",
    ):
        await OperatorEnricherStrategy(engine).enrich(node, constraints)


@pytest.mark.asyncio
async def test_enrich_operator_classical_input(engine: AsyncEngine) -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="==")
    constraints = Constraints(
        requested_inputs={0: FloatType(size=32), 1: FloatType(size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    with pytest.raises(
        InputTypeMismatch,
        match=r"^Expected type 'qubit' for input 0\. Got 'FloatType\(size=32\)'\.$",
    ):
        await OperatorEnricherStrategy(engine).enrich(node, constraints)


@pytest.mark.asyncio
async def test_enrich_operator_node_not_in_db(engine: AsyncEngine) -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="&")
    constraints = Constraints(
        requested_inputs={0: QubitType(size=5), 1: QubitType(size=6)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    assert (await OperatorEnricherStrategy(engine).enrich(node, constraints)) == []

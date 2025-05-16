import pytest
from sqlalchemy.orm import Session

from app.enricher import (
    Constraints,
    ConstraintValidationException,
    NodeUnsupportedException,
)
from app.enricher.models import InputType, NodeType, OperatorNode, OperatorType
from app.enricher.operator import OperatorEnricherStrategy
from app.model.CompileRequest import OperatorNode as FrontendOperatorNode
from app.model.CompileRequest import PrepareStateNode as FrontendPrepareStateNode
from app.model.data_types import FloatType, QubitType


@pytest.fixture(autouse=True)
def setup_database_data(session: Session) -> None:
    """
    Set up the database with test data for the EncodeValueNode.
    """
    node1 = OperatorNode(
        type=NodeType.OPERATOR,
        depth=1,
        width=2,
        implementation="addition_impl",
        inputs=[
            {"index": 0, "type": InputType.QubitType.value, "size": 2},
            {"index": 1, "type": InputType.QubitType.value, "size": 3},
        ],
        operator=OperatorType.ADD,
    )
    node2 = OperatorNode(
        type=NodeType.OPERATOR,
        depth=2,
        width=2,
        implementation="multiplication_impl",
        inputs=[
            {"index": 0, "type": InputType.QubitType.value, "size": 1},
            {"index": 1, "type": InputType.QubitType.value, "size": 4},
        ],
        operator=OperatorType.MUL,
    )
    node3 = OperatorNode(
        type=NodeType.OPERATOR,
        depth=3,
        width=3,
        implementation="or_impl",
        inputs=[
            {"index": 0, "type": InputType.QubitType.value, "size": 4},
            {"index": 1, "type": InputType.QubitType.value, "size": 3},
        ],
        operator=OperatorType.OR,
    )
    node4 = OperatorNode(
        type=NodeType.OPERATOR,
        depth=3,
        width=4,
        implementation="greater_than_impl",
        inputs=[
            {"index": 0, "type": InputType.QubitType.value, "size": 5},
            {"index": 1, "type": InputType.QubitType.value, "size": 4},
        ],
        operator=OperatorType.GT,
    )
    node5 = OperatorNode(
        type=NodeType.OPERATOR,
        depth=4,
        width=5,
        implementation="minimum_impl",
        inputs=[
            {"index": 0, "type": InputType.QubitType.value, "size": 5},
            {"index": 1, "type": InputType.QubitType.value, "size": 6},
        ],
        operator=OperatorType.MIN,
    )

    session.add_all([node1, node2, node3, node4, node5])
    session.commit()
    session.close()


@pytest.mark.asyncio
async def test_enrich_plus_operator() -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="+")
    constraints = Constraints(
        requested_inputs={0: QubitType(reg_size=2), 1: QubitType(reg_size=3)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await OperatorEnricherStrategy().enrich(node, constraints)

    assert result is not None
    assert result.enriched_node.implementation == "addition_impl"
    assert result.meta_data.width == 1
    assert result.meta_data.depth == 2  # noqa: PLR2004


@pytest.mark.asyncio
async def test_enrich_multiplication_operator() -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="*")
    constraints = Constraints(
        requested_inputs={0: QubitType(reg_size=1), 1: QubitType(reg_size=4)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await OperatorEnricherStrategy().enrich(node, constraints)

    assert result is not None
    assert result.enriched_node.implementation == "multiplication_impl"
    assert result.meta_data.width == 2  # noqa: PLR2004
    assert result.meta_data.depth == 2  # noqa: PLR2004


@pytest.mark.asyncio
async def test_enrich_OR_operator() -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="|")
    constraints = Constraints(
        requested_inputs={0: QubitType(reg_size=4), 1: QubitType(reg_size=3)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await OperatorEnricherStrategy().enrich(node, constraints)

    assert result is not None
    assert result.enriched_node.implementation == "or_impl"
    assert result.meta_data.width == 3  # noqa: PLR2004
    assert result.meta_data.depth == 3  # noqa: PLR2004


@pytest.mark.asyncio
async def test_enrich_greater_operator() -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator=">")
    constraints = Constraints(
        requested_inputs={0: QubitType(reg_size=5), 1: QubitType(reg_size=4)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await OperatorEnricherStrategy().enrich(node, constraints)

    assert result is not None
    assert result.enriched_node.implementation == "greater_than_impl"
    assert result.meta_data.width == 4  # noqa: PLR2004
    assert result.meta_data.depth == 3  # noqa: PLR2004


@pytest.mark.asyncio
async def test_enrich_min_operator() -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="min")
    constraints = Constraints(
        requested_inputs={0: QubitType(reg_size=5), 1: QubitType(reg_size=6)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await OperatorEnricherStrategy().enrich(node, constraints)

    assert result is not None
    assert result.enriched_node.implementation == "minimum_impl"
    assert result.meta_data.width == 4  # noqa: PLR2004
    assert result.meta_data.depth == 5  # noqa: PLR2004


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
        await OperatorEnricherStrategy().enrich(node, constraints)


@pytest.mark.asyncio
async def test_enrich_operator_one_inputs() -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="!=")
    constraints = Constraints(
        requested_inputs={0: QubitType(reg_size=7)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    with pytest.raises(
        ConstraintValidationException,
        match=r"^OperatorNode can only have a two inputs$",
    ):
        await OperatorEnricherStrategy().enrich(node, constraints)


@pytest.mark.asyncio
async def test_enrich_operator_classical_input() -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="==")
    constraints = Constraints(
        requested_inputs={0: FloatType(bit_size=32), 1: FloatType(bit_size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    with pytest.raises(
        ConstraintValidationException,
        match=r"^OperatorNode only supports qubit types$",
    ):
        await OperatorEnricherStrategy().enrich(node, constraints)


@pytest.mark.asyncio
async def test_enrich_operator_node_not_in_db() -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="&")
    constraints = Constraints(
        requested_inputs={0: QubitType(reg_size=5), 1: QubitType(reg_size=6)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    with pytest.raises(
        RuntimeError,
        match=r"^No results found in the database$",
    ):
        await OperatorEnricherStrategy().enrich(node, constraints)

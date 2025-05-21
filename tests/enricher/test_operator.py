from collections.abc import Iterable

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.enricher import (
    Constraints,
    ConstraintValidationException,
    EnrichmentResult,
)
from app.enricher.models import Input, InputType, NodeType, OperatorNode, OperatorType
from app.enricher.operator import OperatorEnricherStrategy
from app.model.CompileRequest import OperatorNode as FrontendOperatorNode
from app.model.CompileRequest import PrepareStateNode as FrontendPrepareStateNode
from app.model.data_types import FloatType, QubitType


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
async def test_enrich_plus_operator() -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="+")
    constraints = Constraints(
        requested_inputs={0: QubitType(reg_size=2), 1: QubitType(reg_size=3)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await OperatorEnricherStrategy().enrich(node, constraints)
    assert_enrichment(result, "addition_impl", 2, 1)


@pytest.mark.asyncio
async def test_enrich_multiplication_operator() -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="*")
    constraints = Constraints(
        requested_inputs={0: QubitType(reg_size=1), 1: QubitType(reg_size=4)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await OperatorEnricherStrategy().enrich(node, constraints)
    assert_enrichment(result, "multiplication_impl", 2, 2)


@pytest.mark.asyncio
async def test_enrich_OR_operator() -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="|")
    constraints = Constraints(
        requested_inputs={0: QubitType(reg_size=4), 1: QubitType(reg_size=3)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await OperatorEnricherStrategy().enrich(node, constraints)
    assert_enrichment(result, "or_impl", 3, 3)


@pytest.mark.asyncio
async def test_enrich_greater_operator() -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator=">")
    constraints = Constraints(
        requested_inputs={0: QubitType(reg_size=5), 1: QubitType(reg_size=4)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await OperatorEnricherStrategy().enrich(node, constraints)
    assert_enrichment(result, "greater_than_impl", 4, 3)


@pytest.mark.asyncio
async def test_enrich_min_operator() -> None:
    node = FrontendOperatorNode(id="1", label=None, type="operator", operator="min")
    constraints = Constraints(
        requested_inputs={0: QubitType(reg_size=5), 1: QubitType(reg_size=6)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    result = await OperatorEnricherStrategy().enrich(node, constraints)
    assert_enrichment(result, "minimum_impl", 5, 4)


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

    result = await OperatorEnricherStrategy().enrich(node, constraints)

    assert result == []


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

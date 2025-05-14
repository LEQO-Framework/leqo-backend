from textwrap import dedent

import pytest

from app.enricher import (
    Constraints,
    ConstraintValidationException,
    NodeUnsupportedException,
)
from app.enricher.merger import MergerEnricherStrategy
from app.model.CompileRequest import (
    ImplementationNode,
    IntLiteralNode,
    MergerNode,
)
from app.model.data_types import IntType, QubitType


def assert_enrichment(
    enriched_node: ImplementationNode, id: str, implementation: str
) -> None:
    assert enriched_node.id == id
    assert enriched_node.implementation == dedent(implementation)


@pytest.mark.asyncio
async def test_merger_normal_cases() -> None:
    strategy = MergerEnricherStrategy()
    result = await strategy.enrich(
        MergerNode(id="nodeId", number_of_inputs=2),
        constraints=Constraints(
            requested_inputs={0: QubitType(reg_size=1), 1: QubitType(reg_size=1)},
            optimizeWidth=False,
            optimizeDepth=False,
        ),
    )

    assert_enrichment(
        result.enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        @leqo.input 0
        qubit[1] merger_input_0;
        @leqo.input 1
        qubit[1] merger_input_1;
        @leqo.output 0
        let merger_output = merger_input_0 ++ merger_input_1;
        """,
    )

    result = await strategy.enrich(
        MergerNode(id="nodeId", number_of_inputs=2),
        constraints=Constraints(
            requested_inputs={0: QubitType(reg_size=2), 1: QubitType(reg_size=3)},
            optimizeWidth=False,
            optimizeDepth=False,
        ),
    )

    assert_enrichment(
        result.enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        @leqo.input 0
        qubit[2] merger_input_0;
        @leqo.input 1
        qubit[3] merger_input_1;
        @leqo.output 0
        let merger_output = merger_input_0 ++ merger_input_1;
        """,
    )

    result = await strategy.enrich(
        MergerNode(id="nodeId", number_of_inputs=3),
        constraints=Constraints(
            requested_inputs={
                0: QubitType(reg_size=1),
                1: QubitType(reg_size=2),
                2: QubitType(reg_size=3),
            },
            optimizeWidth=False,
            optimizeDepth=False,
        ),
    )

    assert_enrichment(
        result.enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        @leqo.input 0
        qubit[1] merger_input_0;
        @leqo.input 1
        qubit[2] merger_input_1;
        @leqo.input 2
        qubit[3] merger_input_2;
        @leqo.output 0
        let merger_output = merger_input_0 ++ merger_input_1 ++ merger_input_2;
        """,
    )


@pytest.mark.asyncio
async def test_merger_invalid_node_type() -> None:
    strategy = MergerEnricherStrategy()

    with pytest.raises(NodeUnsupportedException):
        await strategy.enrich(IntLiteralNode(id="nodeId", value=42), constraints=None)


@pytest.mark.asyncio
async def test_merger_no_constraints() -> None:
    strategy = MergerEnricherStrategy()

    with pytest.raises(
        ConstraintValidationException, match=r"^Merger requires at least two inputs\.$"
    ):
        await strategy.enrich(
            MergerNode(id="nodeId", number_of_inputs=2), constraints=None
        )


@pytest.mark.asyncio
async def test_merger_too_few_inputs() -> None:
    strategy = MergerEnricherStrategy()

    with pytest.raises(
        ConstraintValidationException, match=r"^Merger requires at least two inputs\.$"
    ):
        await strategy.enrich(
            MergerNode(id="nodeId", number_of_inputs=2),
            constraints=Constraints(
                requested_inputs={0: QubitType(reg_size=1)},
                optimizeWidth=False,
                optimizeDepth=False,
            ),
        )


@pytest.mark.asyncio
async def test_merger_number_of_inputs_neq_reg_size() -> None:
    strategy = MergerEnricherStrategy()

    with pytest.raises(
        ConstraintValidationException,
        match=r"^MergerNode\.number_of_inputs \([0-9]+\) does not match the amount of provided inputs \([0-9]+\)\.$",
    ):
        await strategy.enrich(
            MergerNode(id="nodeId", number_of_inputs=3),
            constraints=Constraints(
                requested_inputs={0: QubitType(reg_size=1), 1: QubitType(reg_size=1)},
                optimizeWidth=False,
                optimizeDepth=False,
            ),
        )


@pytest.mark.asyncio
async def test_merger_invalid_input_type() -> None:
    strategy = MergerEnricherStrategy()

    with pytest.raises(
        ConstraintValidationException,
        match=r"^Invalid input type at index [0-9]+: expected QubitType, got .+\.$",
    ):
        await strategy.enrich(
            MergerNode(id="nodeId", number_of_inputs=2),
            constraints=Constraints(
                requested_inputs={0: QubitType(reg_size=1), 1: IntType(bit_size=32)},
                optimizeWidth=False,
                optimizeDepth=False,
            ),
        )


@pytest.mark.asyncio
async def test_merger_invalid_register_size() -> None:
    strategy = MergerEnricherStrategy()

    with pytest.raises(
        ConstraintValidationException,
        match=r"^Invalid register size at index [0-9]+: [0-9]+\. Must be >= 1\.$",
    ):
        await strategy.enrich(
            MergerNode(id="nodeId", number_of_inputs=2),
            constraints=Constraints(
                requested_inputs={0: QubitType(reg_size=1), 1: QubitType(reg_size=0)},
                optimizeWidth=False,
                optimizeDepth=False,
            ),
        )

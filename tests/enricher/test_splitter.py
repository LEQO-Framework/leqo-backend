from textwrap import dedent

import pytest

from app.enricher import (
    Constraints,
    ConstraintValidationException,
    NodeUnsupportedException,
)
from app.enricher.splitter import SplitterEnricherStrategy
from app.model.CompileRequest import (
    ImplementationNode,
    IntLiteralNode,
    SplitterNode,
)
from app.model.data_types import IntType, QubitType


def assert_enrichment(
    enriched_node: ImplementationNode, id: str, implementation: str
) -> None:
    assert enriched_node.id == id
    assert enriched_node.implementation == dedent(implementation)


@pytest.mark.asyncio
async def test_splitter_normal_cases() -> None:
    strategy = SplitterEnricherStrategy()

    result = await strategy.enrich(
        SplitterNode(id="nodeId", numberOutputs=2),
        constraints=Constraints(
            requested_inputs={0: QubitType(reg_size=2)},
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
        qubit[2] splitter_input;
        @leqo.output 0
        let splitter_output_0 = splitter_input[{0}];
        @leqo.output 1
        let splitter_output_1 = splitter_input[{1}];
        """,
    )

    result = await strategy.enrich(
        SplitterNode(id="nodeId", numberOutputs=3),
        constraints=Constraints(
            requested_inputs={0: QubitType(reg_size=3)},
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
        qubit[3] splitter_input;
        @leqo.output 0
        let splitter_output_0 = splitter_input[{0}];
        @leqo.output 1
        let splitter_output_1 = splitter_input[{1}];
        @leqo.output 2
        let splitter_output_2 = splitter_input[{2}];
        """,
    )


@pytest.mark.asyncio
async def test_splitter_invalid_node_type() -> None:
    strategy = SplitterEnricherStrategy()

    with pytest.raises(NodeUnsupportedException):
        await strategy.enrich(IntLiteralNode(id="nodeId", value=42), constraints=None)


@pytest.mark.asyncio
async def test_splitter_no_constraints() -> None:
    strategy = SplitterEnricherStrategy()

    with pytest.raises(
        ConstraintValidationException, match=r"^Splitter requires exactly one input\.$"
    ):
        await strategy.enrich(
            SplitterNode(id="nodeId", numberOutputs=2), constraints=None
        )


@pytest.mark.asyncio
async def test_splitter_no_inputs() -> None:
    strategy = SplitterEnricherStrategy()

    with pytest.raises(
        ConstraintValidationException, match=r"^Splitter requires exactly one input\.$"
    ):
        await strategy.enrich(
            SplitterNode(id="nodeId", numberOutputs=2),
            constraints=Constraints(
                requested_inputs={},
                optimizeWidth=False,
                optimizeDepth=False,
            ),
        )


@pytest.mark.asyncio
async def test_splitter_too_many_inputs() -> None:
    strategy = SplitterEnricherStrategy()

    with pytest.raises(
        ConstraintValidationException, match=r"^Splitter requires exactly one input\.$"
    ):
        await strategy.enrich(
            SplitterNode(id="nodeId", numberOutputs=2),
            constraints=Constraints(
                requested_inputs={0: QubitType(reg_size=1), 1: QubitType(reg_size=1)},
                optimizeWidth=False,
                optimizeDepth=False,
            ),
        )


@pytest.mark.asyncio
async def test_splitter_invalid_input_type() -> None:
    strategy = SplitterEnricherStrategy()

    with pytest.raises(
        ConstraintValidationException,
        match=r"^Invalid input type: expected QubitType, got .+\.$",
    ):
        await strategy.enrich(
            SplitterNode(id="nodeId", numberOutputs=2),
            constraints=Constraints(
                requested_inputs={0: IntType(bit_size=32)},
                optimizeWidth=False,
                optimizeDepth=False,
            ),
        )


@pytest.mark.asyncio
async def test_splitter_invalid_register_size() -> None:
    strategy = SplitterEnricherStrategy()

    with pytest.raises(
        ConstraintValidationException,
        match=r"^Invalid register size: [0-9]+\. Must be >= 1\.$",
    ):
        await strategy.enrich(
            SplitterNode(id="nodeId", numberOutputs=2),
            constraints=Constraints(
                requested_inputs={0: QubitType(reg_size=0)},
                optimizeWidth=False,
                optimizeDepth=False,
            ),
        )


@pytest.mark.asyncio
async def test_splitter_number_of_outputs_neq_reg_size() -> None:
    strategy = SplitterEnricherStrategy()

    with pytest.raises(
        ConstraintValidationException,
        match=r"^SplitterNode\.numberOutputs \([0-9]+\) does not match input register size \([0-9]+\)\.$",
    ):
        await strategy.enrich(
            SplitterNode(id="nodeId", numberOutputs=2),
            constraints=Constraints(
                requested_inputs={0: QubitType(reg_size=3)},
                optimizeWidth=False,
                optimizeDepth=False,
            ),
        )

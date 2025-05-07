from textwrap import dedent

import pytest

from app.enricher.literals import LiteralEnricherStrategy
from app.model.CompileRequest import (
    BitLiteralNode,
    BoolLiteralNode,
    FloatLiteralNode,
    ImplementationNode,
    IntLiteralNode,
    QubitNode,
)


def assert_enrichment(
    enriched_node: ImplementationNode, id: str, implementation: str
) -> None:
    assert enriched_node.id == id
    assert enriched_node.implementation == dedent(implementation)


@pytest.mark.asyncio
async def test_qubit_literal() -> None:
    strategy = LiteralEnricherStrategy()
    result = await strategy.enrich(QubitNode(id="nodeId"), constraints=None)

    assert_enrichment(
        result.enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        qubit[1] literal;
        @leqo.output 0
        let out = literal;
        """,
    )

    result = await strategy.enrich(QubitNode(id="nodeId", size=42), constraints=None)

    assert_enrichment(
        result.enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        qubit[42] literal;
        @leqo.output 0
        let out = literal;
        """,
    )


@pytest.mark.asyncio
async def test_int_literal() -> None:
    strategy = LiteralEnricherStrategy()
    result = await strategy.enrich(
        IntLiteralNode(id="nodeId", value=123), constraints=None
    )

    assert_enrichment(
        result.enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        int[32] literal = 123;
        @leqo.output 0
        let out = literal;
        """,
    )

    result = await strategy.enrich(
        IntLiteralNode(id="nodeId", value=-123), constraints=None
    )

    assert_enrichment(
        result.enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        int[32] literal = -123;
        @leqo.output 0
        let out = literal;
        """,
    )

    result = await strategy.enrich(
        IntLiteralNode(id="nodeId", value=123, bitSize=64), constraints=None
    )

    assert_enrichment(
        result.enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        int[64] literal = 123;
        @leqo.output 0
        let out = literal;
        """,
    )


@pytest.mark.asyncio
async def test_float_literal() -> None:
    strategy = LiteralEnricherStrategy()
    result = await strategy.enrich(
        FloatLiteralNode(id="nodeId", value=123.5), constraints=None
    )

    assert_enrichment(
        result.enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        float[32] literal = 123.5;
        @leqo.output 0
        let out = literal;
        """,
    )

    result = await strategy.enrich(
        FloatLiteralNode(id="nodeId", value=-123.5), constraints=None
    )

    assert_enrichment(
        result.enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        float[32] literal = -123.5;
        @leqo.output 0
        let out = literal;
        """,
    )

    result = await strategy.enrich(
        FloatLiteralNode(id="nodeId", value=123.5, bitSize=64), constraints=None
    )

    assert_enrichment(
        result.enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        float[64] literal = 123.5;
        @leqo.output 0
        let out = literal;
        """,
    )


@pytest.mark.asyncio
async def test_bit_literal() -> None:
    strategy = LiteralEnricherStrategy()
    result = await strategy.enrich(
        BitLiteralNode(id="nodeId", value=0), constraints=None
    )

    assert_enrichment(
        result.enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        bit literal = 0;
        @leqo.output 0
        let out = literal;
        """,
    )

    result = await strategy.enrich(
        BitLiteralNode(id="nodeId", value=1), constraints=None
    )

    assert_enrichment(
        result.enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        bit literal = 1;
        @leqo.output 0
        let out = literal;
        """,
    )


@pytest.mark.asyncio
async def test_bool_literal() -> None:
    strategy = LiteralEnricherStrategy()
    result = await strategy.enrich(
        BoolLiteralNode(id="nodeId", value=False), constraints=None
    )

    assert_enrichment(
        result.enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        bool literal = false;
        @leqo.output 0
        let out = literal;
        """,
    )

    result = await strategy.enrich(
        BoolLiteralNode(id="nodeId", value=True), constraints=None
    )

    assert_enrichment(
        result.enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        bool literal = true;
        @leqo.output 0
        let out = literal;
        """,
    )

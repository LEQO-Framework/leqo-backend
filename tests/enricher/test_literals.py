import pytest

from app.enricher.literals import LiteralEnricherStrategy
from app.model.CompileRequest import (
    BitLiteralNode,
    BoolLiteralNode,
    FloatLiteralNode,
    IntLiteralNode,
    QubitNode,
)
from tests.enricher.utils import assert_enrichment


@pytest.mark.asyncio
async def test_qubit_literal() -> None:
    strategy = LiteralEnricherStrategy()
    result = list(await strategy.enrich(QubitNode(id="nodeId"), constraints=None))

    assert len(result) == 1
    assert_enrichment(
        result[0].enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        qubit[1] literal;
        @leqo.output 0
        let out = literal;
        """,
    )

    result = list(
        await strategy.enrich(QubitNode(id="nodeId", size=42), constraints=None)
    )

    assert len(result) == 1
    assert_enrichment(
        result[0].enriched_node,
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
    result = list(
        await strategy.enrich(IntLiteralNode(id="nodeId", value=123), constraints=None)
    )

    assert len(result) == 1
    assert_enrichment(
        result[0].enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        int[32] literal = 123;
        @leqo.output 0
        let out = literal;
        """,
    )

    result = list(
        await strategy.enrich(IntLiteralNode(id="nodeId", value=-123), constraints=None)
    )

    assert len(result) == 1
    assert_enrichment(
        result[0].enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        int[32] literal = -123;
        @leqo.output 0
        let out = literal;
        """,
    )

    result = list(
        await strategy.enrich(
            IntLiteralNode(id="nodeId", value=123, bitSize=64), constraints=None
        )
    )

    assert len(result) == 1
    assert_enrichment(
        result[0].enriched_node,
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
    result = list(
        await strategy.enrich(
            FloatLiteralNode(id="nodeId", value=123.5), constraints=None
        )
    )

    assert len(result) == 1
    assert_enrichment(
        result[0].enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        float[32] literal = 123.5;
        @leqo.output 0
        let out = literal;
        """,
    )

    result = list(
        await strategy.enrich(
            FloatLiteralNode(id="nodeId", value=-123.5), constraints=None
        )
    )

    assert len(result) == 1
    assert_enrichment(
        result[0].enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        float[32] literal = -123.5;
        @leqo.output 0
        let out = literal;
        """,
    )

    result = list(
        await strategy.enrich(
            FloatLiteralNode(id="nodeId", value=123.5, bitSize=64), constraints=None
        )
    )

    assert len(result) == 1
    assert_enrichment(
        result[0].enriched_node,
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
    result = list(
        await strategy.enrich(BitLiteralNode(id="nodeId", value=0), constraints=None)
    )

    assert len(result) == 1
    assert_enrichment(
        result[0].enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        bit literal = 0;
        @leqo.output 0
        let out = literal;
        """,
    )

    result = list(
        await strategy.enrich(BitLiteralNode(id="nodeId", value=1), constraints=None)
    )

    assert len(result) == 1
    assert_enrichment(
        result[0].enriched_node,
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
    result = list(
        await strategy.enrich(
            BoolLiteralNode(id="nodeId", value=False), constraints=None
        )
    )

    assert len(result) == 1
    assert_enrichment(
        result[0].enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        bool literal = false;
        @leqo.output 0
        let out = literal;
        """,
    )

    result = list(
        await strategy.enrich(
            BoolLiteralNode(id="nodeId", value=True), constraints=None
        )
    )

    assert len(result) == 1
    assert_enrichment(
        result[0].enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        bool literal = true;
        @leqo.output 0
        let out = literal;
        """,
    )

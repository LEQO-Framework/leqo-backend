import asyncio
from typing import override

import pytest

from app.enricher import (
    Constraints,
    Enricher,
    EnricherStrategy,
    EnrichmentResult,
    ImplementationMetaData,
    NodeUnsupportedException,
)
from app.model.CompileRequest import (
    BitLiteralNode,
    BoolLiteralNode,
    FloatLiteralNode,
    ImplementationNode,
    IntLiteralNode,
)
from app.model.CompileRequest import (
    Node as FrontendNode,
)


class IntToAEnricherStrategy(EnricherStrategy):
    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> EnrichmentResult:
        if not isinstance(node, IntLiteralNode):
            raise NodeUnsupportedException(node)

        return EnrichmentResult(
            ImplementationNode(id=node.id, implementation="A"),
            ImplementationMetaData(width=None, depth=None),
        )


class FloatToBEnricherStrategy(EnricherStrategy):
    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> EnrichmentResult:
        if not isinstance(node, FloatLiteralNode):
            raise NodeUnsupportedException(node)

        return EnrichmentResult(
            ImplementationNode(id=node.id, implementation="B"),
            ImplementationMetaData(width=None, depth=None),
        )


class AsyncEnricherStrategy(EnricherStrategy):
    @override
    async def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> EnrichmentResult:
        if not isinstance(node, BitLiteralNode):
            raise NodeUnsupportedException(node)

        await asyncio.create_task(asyncio.sleep(1))
        return EnrichmentResult(
            ImplementationNode(id=node.id, implementation="C"),
            ImplementationMetaData(width=None, depth=None),
        )


@pytest.mark.asyncio
async def test_strategy_enrich_known_node() -> None:
    strategy = IntToAEnricherStrategy()
    result = list(
        await strategy.enrich(IntLiteralNode(id="nodeId", value=42), constraints=None)
    )

    assert len(result) == 1
    assert result[0].enriched_node is not None
    assert result[0].enriched_node.id == "nodeId"
    assert result[0].enriched_node.implementation == "A"


@pytest.mark.asyncio
async def test_strategy_enrich_unknown_node() -> None:
    strategy = IntToAEnricherStrategy()
    with pytest.raises(
        NodeUnsupportedException, match="^Node 'FloatLiteralNode' is not supported$"
    ):
        await strategy.enrich(
            FloatLiteralNode(id="nodeId", value=42.0), constraints=None
        )


@pytest.mark.asyncio
async def test_enrich_known_node() -> None:
    enricher = Enricher(
        IntToAEnricherStrategy(), FloatToBEnricherStrategy(), AsyncEnricherStrategy()
    )
    enriched_node = await enricher.enrich(
        IntLiteralNode(id="nodeId", value=42), constraints=None
    )

    assert enriched_node.id == "nodeId"
    assert enriched_node.implementation == "A"

    enriched_node = await enricher.enrich(
        FloatLiteralNode(id="nodeId2", value=42.0), constraints=None
    )

    assert enriched_node.id == "nodeId2"
    assert enriched_node.implementation == "B"

    enriched_node = await enricher.enrich(
        BitLiteralNode(id="nodeId3", value=0), constraints=None
    )

    assert enriched_node.id == "nodeId3"
    assert enriched_node.implementation == "C"


@pytest.mark.asyncio
async def test_try_enrich_known_node() -> None:
    enricher = Enricher(
        IntToAEnricherStrategy(), FloatToBEnricherStrategy(), AsyncEnricherStrategy()
    )
    enriched_node = await enricher.try_enrich(
        IntLiteralNode(id="nodeId", value=42), constraints=None
    )

    assert enriched_node is not None
    assert enriched_node.id == "nodeId"
    assert enriched_node.implementation == "A"

    enriched_node = await enricher.try_enrich(
        FloatLiteralNode(id="nodeId2", value=42.0), constraints=None
    )

    assert enriched_node is not None
    assert enriched_node.id == "nodeId2"
    assert enriched_node.implementation == "B"

    enriched_node = await enricher.try_enrich(
        BitLiteralNode(id="nodeId3", value=0), constraints=None
    )

    assert enriched_node is not None
    assert enriched_node.id == "nodeId3"
    assert enriched_node.implementation == "C"


@pytest.mark.asyncio
async def test_try_enrich_unknown_node() -> None:
    enricher = Enricher(IntToAEnricherStrategy(), FloatToBEnricherStrategy())
    enriched_node = await enricher.try_enrich(
        BoolLiteralNode(id="nodeId", value=False), constraints=None
    )

    assert enriched_node is None


@pytest.mark.asyncio
async def test_enrich_unknown_node() -> None:
    enricher = Enricher(IntToAEnricherStrategy(), FloatToBEnricherStrategy())
    with pytest.raises(
        ExceptionGroup,
        match=r"^Enrichment for node 'nodeId' failed \(2 sub-exceptions\)$",
    ) as ex:
        await enricher.enrich(
            BoolLiteralNode(id="nodeId", value=False), constraints=None
        )

    assert len(ex.value.exceptions) == 2  # noqa: PLR2004 Magic value used in comparison
    assert isinstance(ex.value.exceptions[0], NodeUnsupportedException)
    assert isinstance(ex.value.exceptions[1], NodeUnsupportedException)

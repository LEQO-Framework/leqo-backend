from typing import override

import pytest

from app.enricher import (
    Constraints,
    Enricher,
    EnricherStrategy,
    EnrichmentResult,
    ImplementationMetaData,
)
from app.model.CompileRequest import (
    BitLiteralNode,
    ImplementationNode,
)
from app.model.CompileRequest import (
    Node as FrontendNode,
)


class EnricherStrategyDummy(EnricherStrategy):
    result: str
    width: int | None
    depth: int | None

    def __init__(self, result: str, width: int | None, depth: int | None):
        self.result = result
        self.width = width
        self.depth = depth

    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> EnrichmentResult:
        return EnrichmentResult(
            ImplementationNode(id=node.id, implementation=self.result),
            ImplementationMetaData(width=self.width, depth=self.depth),
        )


@pytest.fixture
def test_enricher() -> Enricher:
    return Enricher(
        EnricherStrategyDummy("42_n", 42, None),
        EnricherStrategyDummy("n_0", None, 0),
        EnricherStrategyDummy("42_0", 42, 0),
        EnricherStrategyDummy("0_42", 0, 42),
        EnricherStrategyDummy("0_n", 0, None),
        EnricherStrategyDummy("n_42", None, 42),
        EnricherStrategyDummy("42_42", 42, 42),
        EnricherStrategyDummy("n_n", None, None),
    )


@pytest.mark.asyncio
async def test_enrich_no_constraints(test_enricher: Enricher) -> None:
    enriched_node = await test_enricher.enrich(
        BitLiteralNode(id="nodeId", value=0), constraints=None
    )

    assert enriched_node.implementation == "0_42"


@pytest.mark.asyncio
async def test_enrich_no_optimize(test_enricher: Enricher) -> None:
    enriched_node = await test_enricher.enrich(
        BitLiteralNode(id="nodeId", value=0),
        constraints=Constraints(
            requested_inputs={}, optimizeWidth=False, optimizeDepth=False
        ),
    )

    assert enriched_node.implementation == "0_42"


@pytest.mark.asyncio
async def test_enrich_optimize_width(test_enricher: Enricher) -> None:
    enriched_node = await test_enricher.enrich(
        BitLiteralNode(id="nodeId", value=0),
        constraints=Constraints(
            requested_inputs={}, optimizeWidth=True, optimizeDepth=False
        ),
    )

    assert enriched_node.implementation == "0_42"


@pytest.mark.asyncio
async def test_enrich_optimize_depth(test_enricher: Enricher) -> None:
    enriched_node = await test_enricher.enrich(
        BitLiteralNode(id="nodeId", value=0),
        constraints=Constraints(
            requested_inputs={}, optimizeWidth=False, optimizeDepth=True
        ),
    )

    assert enriched_node.implementation == "42_0"


@pytest.mark.asyncio
async def test_enrich_optimize_both(test_enricher: Enricher) -> None:
    enriched_node = await test_enricher.enrich(
        BitLiteralNode(id="nodeId", value=0),
        constraints=Constraints(
            requested_inputs={}, optimizeWidth=True, optimizeDepth=True
        ),
    )

    assert enriched_node.implementation == "0_42"

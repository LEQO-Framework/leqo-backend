"""
Stub strategy for workflow enrichment.

Currently acts as a no-op placeholder. It does not enrich any node,
but provides an extension point for future workflow-specific logic.
"""

from typing import Iterable, override

from app.enricher import (
    Constraints,
    EnricherStrategy,
    EnrichmentResult,
)
from app.model.CompileRequest import Node as FrontendNode


class WorkflowEnricherStrategy(EnricherStrategy):
    """
    Placeholder strategy for workflow-targeted enrichment.

    Returns no results for now. Add logic here to generate workflow-specific
    enrichments if needed in the future.
    """

    @override
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> Iterable[EnrichmentResult]:
        return []


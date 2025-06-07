from collections.abc import Iterable
from textwrap import dedent

from app.enricher import EnrichmentResult, ParsedImplementationNode
from app.model.CompileRequest import ImplementationNode
from app.openqasm3.printer import leqo_dumps


def assert_enrichment(
    enriched_node: ImplementationNode | ParsedImplementationNode,
    id: str,
    implementation: str,
) -> None:
    impl = enriched_node.implementation
    impl_str = impl if isinstance(impl, str) else leqo_dumps(impl)
    assert enriched_node.id == id
    assert impl_str == dedent(implementation)


def assert_enrichments(
    enrichment_result: Iterable[EnrichmentResult],
    expected_implementation: str,
    expected_width: int,
    expected_depth: int,
) -> None:
    for result in enrichment_result:
        impl = result.enriched_node.implementation
        impl_str = impl if isinstance(impl, str) else leqo_dumps(impl)
        assert impl_str == expected_implementation
        assert result.meta_data.width == expected_width
        assert result.meta_data.depth == expected_depth

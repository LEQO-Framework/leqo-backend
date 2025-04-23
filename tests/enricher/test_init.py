from io import UnsupportedOperation
from typing import override

import pytest

from app.enricher import AggregateEnricher, Constraints, Enricher, empty_constraints
from app.model.CompileRequest import (
    BoolLiteralNode,
    FloatLiteralNode,
    ImplementationNode,
    IntLiteralNode,
    Node,
)


class IntToAEnricher(Enricher):
    @override
    def try_enrich(
        self, node: Node, _constraints: Constraints
    ) -> ImplementationNode | None:
        if not isinstance(node, IntLiteralNode):
            return None

        return ImplementationNode(id=node.id, implementation="A")


class FloatToBEnricher(Enricher):
    @override
    def try_enrich(
        self, node: Node, _constraints: Constraints
    ) -> ImplementationNode | None:
        if not isinstance(node, FloatLiteralNode):
            return None

        return ImplementationNode(id=node.id, implementation="B")


def test_try_enrich_known_node() -> None:
    enricher = IntToAEnricher()
    enriched_node = enricher.try_enrich(
        IntLiteralNode(id="nodeId", value=42), empty_constraints()
    )

    assert enriched_node is not None
    assert enriched_node.id == "nodeId"
    assert enriched_node.implementation == "A"


def test_enrich_known_node() -> None:
    enricher = IntToAEnricher()
    enriched_node = enricher.enrich(
        IntLiteralNode(id="nodeId", value=42), empty_constraints()
    )

    assert enriched_node is not None
    assert enriched_node.id == "nodeId"
    assert enriched_node.implementation == "A"


def test_try_enrich_unknown_node() -> None:
    enricher = IntToAEnricher()
    enriched_node = enricher.try_enrich(
        FloatLiteralNode(id="nodeId", value=42.0), empty_constraints()
    )

    assert enriched_node is None


def test_enrich_unknown_node() -> None:
    enricher = IntToAEnricher()
    with pytest.raises(
        UnsupportedOperation, match="^Unsupported node 'FloatLiteralNode'$"
    ):
        enricher.enrich(FloatLiteralNode(id="nodeId", value=42.0), empty_constraints())


def test_aggregate_enrich_known_node() -> None:
    enricher = AggregateEnricher(IntToAEnricher(), FloatToBEnricher())
    enriched_node = enricher.enrich(
        IntLiteralNode(id="nodeId", value=42), empty_constraints()
    )

    assert enriched_node.id == "nodeId"
    assert enriched_node.implementation == "A"

    enriched_node = enricher.enrich(
        FloatLiteralNode(id="nodeId2", value=42.0), empty_constraints()
    )

    assert enriched_node.id == "nodeId2"
    assert enriched_node.implementation == "B"


def test_aggregate_try_enrich_known_node() -> None:
    enricher = AggregateEnricher(IntToAEnricher(), FloatToBEnricher())
    enriched_node = enricher.try_enrich(
        IntLiteralNode(id="nodeId", value=42), empty_constraints()
    )

    assert enriched_node is not None
    assert enriched_node.id == "nodeId"
    assert enriched_node.implementation == "A"

    enriched_node = enricher.try_enrich(
        FloatLiteralNode(id="nodeId2", value=42.0), empty_constraints()
    )

    assert enriched_node is not None
    assert enriched_node.id == "nodeId2"
    assert enriched_node.implementation == "B"


def test_aggregate_try_enrich_unknown_node() -> None:
    enricher = AggregateEnricher(IntToAEnricher(), FloatToBEnricher())
    enriched_node = enricher.try_enrich(
        BoolLiteralNode(id="nodeId", value=False), empty_constraints()
    )

    assert enriched_node is None


def test_aggregate_enrich_unknown_node() -> None:
    enricher = AggregateEnricher(IntToAEnricher(), FloatToBEnricher())
    with pytest.raises(
        UnsupportedOperation, match="^Unsupported node 'BoolLiteralNode'$"
    ):
        enricher.enrich(BoolLiteralNode(id="nodeId", value=False), empty_constraints())

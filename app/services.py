from collections.abc import Callable
from uuid import UUID, uuid4

from app.enricher import Enricher
from app.enricher.literals import LiteralEnricherStrategy
from app.enricher.measure import MeasurementEnricherStrategy
from app.enricher.merger import MergerEnricherStrategy
from app.enricher.splitter import SplitterEnricherStrategy


def get_enricher() -> Enricher:
    return Enricher(
        LiteralEnricherStrategy(),
        MeasurementEnricherStrategy(),
        SplitterEnricherStrategy(),
        MergerEnricherStrategy(),
    )


NodeIdFactory = Callable[[str], UUID]


def get_node_id_factory() -> NodeIdFactory:
    def node_id_factory(_node_id: str) -> UUID:
        return uuid4()

    return node_id_factory

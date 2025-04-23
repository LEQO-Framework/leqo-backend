"""
The enrichment module provides the abstract capability of "enriching" :class:`~app.model.CompileRequest.Node` with an openqasm implementation
(See :class:`~app.model.CompileRequest.ImplementationNode`).

The enrichment can be controlled by specifying :class:`~app.enricher.Constraints`.

Multiple enrichment-services can be connected to the backend by supplying implementations of :class:`~app.enricher.Enricher`.
Some services could read implementations from a database or generate them on the fly.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from io import UnsupportedOperation

from app.model.CompileRequest import (
    ImplementationNode,
    Node,
)
from app.processing.graph import ClassicalIOInstance, QubitIOInstance


@dataclass
class Constraints:
    """
    Constraints to follow during enrichment.
    """

    requested_inputs: list[QubitIOInstance | ClassicalIOInstance]


def empty_constraints() -> Constraints:
    """
    Returns a set of empty constraints.
    """

    return Constraints([])


class Enricher(ABC):
    """
    An enrichment-unit capable of enriching some nodes.
    """

    @abstractmethod
    def try_enrich(
        self, node: Node, constraints: Constraints
    ) -> ImplementationNode | None:
        """
        Tries to enrich the given node according to the specified constraints.
        Returns none if enrichment is not possible.

        :param node: The node to enrich.
        :param constraints: Constraints to follow during enrichment.
        :return: The enriched node or none if no enriched can be found.
        """
        raise NotImplementedError()

    def enrich(self, node: Node, constraints: Constraints) -> ImplementationNode:
        """
        Enrich the given node according to the specified constraints.
        Throws if enrichment is not possible.

        :param node: The node to enrich.
        :param constraints: Constraints to follow during enrichment.
        :return: The enriched node.
        """

        enriched = self.try_enrich(node, constraints)
        if enriched is not None:
            return enriched

        raise UnsupportedOperation(f"Unsupported node '{type(node).__name__}'")


class AggregateEnricher(Enricher):
    """
    An :class:`~app.enricher.Enricher` that combines multiple enrichers into one.
    """

    enrichers: list[Enricher]

    def __init__(self, *enrichers: Enricher):
        self.enrichers = list(enrichers)

    def try_enrich(
        self, node: Node, constraints: Constraints
    ) -> ImplementationNode | None:
        for enricher in self.enrichers:
            enriched = enricher.try_enrich(node, constraints)
            if enriched is not None:
                return enriched

        return None

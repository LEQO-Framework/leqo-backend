"""
The enrichment module provides the abstract capability of "enriching" :class:`~app.model.CompileRequest.Node` with an openqasm implementation
(See :class:`~app.model.CompileRequest.ImplementationNode`).

The enrichment can be controlled by specifying :class:`~app.enricher.Constraints`.

Multiple enrichment-services can be connected to the backend by supplying implementations of :class:`~app.enricher.Enricher`.
Some services could read implementations from a database or generate them on the fly.
"""

import asyncio
import math
from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from dataclasses import dataclass

from app.model.CompileRequest import (
    ImplementationNode,
)
from app.model.CompileRequest import (
    Node as FrontendNode,
)
from app.model.data_types import LeqoSupportedType


@dataclass(frozen=True)
class Constraints:
    """
    Constraints to follow during enrichment.
    """

    requested_inputs: dict[int, LeqoSupportedType]
    optimizeWidth: bool
    optimizeDepth: bool


@dataclass(frozen=True)
class ImplementationMetaData:
    """
    Meta-data of a generated implementation.
    """

    width: int | None
    depth: int | None


@dataclass(frozen=True)
class EnrichmentResult:
    """
    Result of an enrichment strategy.
    """

    enriched_node: ImplementationNode
    meta_data: ImplementationMetaData


class EnricherStrategy(ABC):
    """
    An enrichment-unit capable of enriching some nodes.
    """

    @abstractmethod
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> EnrichmentResult | Coroutine[None, None, EnrichmentResult]:
        """
        Implementation of :meth:`~app.enricher.EnricherStrategy.enrich`.
        May return awaitable or result directly.

        :param node: The node to enrich.
        :param constraints: Constraints to follow during enrichment.
        :return: The enriched node or awaitable to enriched node.
        """

        raise NotImplementedError()

    async def enrich(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> EnrichmentResult:
        """
        Enrich the given node according to the specified constraints.
        Throws if enrichment is not possible.

        :param node: The node to enrich.
        :param constraints: Constraints to follow during enrichment.
        :return: The enriched node.
        """

        result = self._enrich_impl(node, constraints)
        if isinstance(result, EnrichmentResult):
            return result
        return await asyncio.create_task(result)


class EnricherException(Exception, ABC):
    """
    Baseclass for exceptions raised by :class:`~app.enricher.EnrichmentStrategy`.
    """


class NodeUnsupportedException(EnricherException):
    """
    Indicates that an :class:`~app.enricher.EnrichmentStrategy` does not support a :class:`~app.model.CompileRequest.Node`.
    """

    def __init__(self, node: FrontendNode):
        super().__init__(f"Node '{type(node).__name__}' is not supported")


class ConstraintValidationException(EnricherException):
    pass


class Enricher:
    """
    Handles multiple :class:`~app.enricher.EnrichmentStrategy`.
    """

    strategies: list[EnricherStrategy]

    def __init__(self, *strategies: EnricherStrategy):
        self.strategies = list(strategies)

    async def try_enrich(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> ImplementationNode | None:
        """
        Tries to enrich a :class:`~app.model.CompileRequest.Node`.
        Returns none on failure.

        :param node: The node to enrich.
        :param constraints: Constraints to follow during enrichment.
        :return: The enriched node or none.
        """

        try:
            return await self.enrich(node, constraints)
        except Exception:
            return None

    async def enrich(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> ImplementationNode:
        """
        Enrich the given :class:`~app.model.CompileRequest.Node` according to the specified :class:`~app.enricher.Constraints`.
        Throws :class:`ExceptionGroup` containing the exceptions from all strategies.

        :param node: The node to enrich.
        :param constraints: Constraints to follow during enrichment.
        :return: Enriched node.
        """

        if isinstance(node, ImplementationNode):
            return node

        results: list[EnrichmentResult] = []
        exceptions: list[Exception] = []

        async for result in asyncio.as_completed(
            x.enrich(node, constraints) for x in self.strategies
        ):
            try:
                results.append(await result)
            except Exception as ex:
                exceptions.append(ex)

        if len(results) == 0:
            raise ExceptionGroup(f"Enrichment for node '{node.id}' failed", exceptions)

        comparer: Callable[[EnrichmentResult], tuple[int | float, int | float]]
        if constraints and constraints.optimizeDepth and not constraints.optimizeWidth:
            comparer = lambda r: (  # noqa: E731 Do not assign a `lambda` expression, use a `def`
                r.meta_data.depth or math.inf,
                r.meta_data.width or math.inf,
            )
        else:
            comparer = lambda r: (  # noqa: E731 Do not assign a `lambda` expression, use a `def`
                r.meta_data.width or math.inf,
                r.meta_data.depth or math.inf,
            )

        results = sorted(results, key=comparer)
        return results[0].enriched_node

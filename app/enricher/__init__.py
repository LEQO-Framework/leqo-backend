"""
The enrichment module provides the abstract capability of "enriching" a :class:`~app.model.CompileRequest.Node` with an openqasm implementation
(See :class:`~app.model.CompileRequest.ImplementationNode`).

The enrichment can be controlled by specifying :class:`~app.enricher.Constraints`.

Multiple "strategies" can be connected to the backend by implementing :class:`~app.enricher.EnricherStrategy`.
Some services could read implementations from a database or generate them on the fly.
"""

import asyncio
import math
from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine, Iterable
from dataclasses import dataclass

from app.model.CompileRequest import (
    ImplementationNode,
)
from app.model.CompileRequest import (
    Node as FrontendNode,
)
from app.model.data_types import LeqoSupportedType
from app.utils import not_none_or


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
    A single unit capable of enriching some nodes.
    Each strategy may choose to only support a subset of supported nodes.
    """

    @abstractmethod
    def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> (
        EnrichmentResult
        | Iterable[EnrichmentResult]
        | Coroutine[None, None, EnrichmentResult]
        | Coroutine[None, None, Iterable[EnrichmentResult]]
    ):
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
    ) -> Iterable[EnrichmentResult]:
        """
        Enrich the given node according to the specified constraints.
        Throws if enrichment is not possible.

        :param node: The node to enrich.
        :param constraints: Constraints to follow during enrichment.
        :return: The enriched node.

        :raises NodeUnsupportedException: If the specified node is not supported by this strategy.
        :raises ConstraintValidationException: The specified constraints are invalid or cannot be met.
        """

        result = self._enrich_impl(node, constraints)
        if isinstance(result, EnrichmentResult):
            return [result]
        if isinstance(result, Iterable):
            return result

        result = await asyncio.create_task(result)

        if isinstance(result, EnrichmentResult):
            return [result]
        if isinstance(result, Iterable):
            return result

        raise Exception("Invalid enrichment result")


class EnricherException(Exception, ABC):
    """
    Baseclass for exceptions raised by :class:`~app.enricher.EnricherStrategy`.
    """


class NodeUnsupportedException(EnricherException):
    """
    Indicates that an :class:`~app.enricher.EnricherStrategy` does not support a :class:`~app.model.CompileRequest.Node`.
    """

    def __init__(self, node: FrontendNode):
        super().__init__(f"Node '{type(node).__name__}' is not supported")


class ConstraintValidationException(EnricherException):
    """
    Indicates that the specified constraints are invalid or cannot be met by an :class:`~app.enricher.EnricherStrategy`.
    """


class InputValidationException(EnricherException):
    """
    Indicates the use-input is not valid (in the context of the given :class:`~app.enricher.Constraints`).
    """


class Enricher:
    """
    Handles multiple :class:`~app.enricher.EnricherStrategy`.
    """

    strategies: list[EnricherStrategy]

    def __init__(self, *strategies: EnricherStrategy):
        self.strategies = list(strategies)

    async def try_enrich(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> ImplementationNode | None:
        """
        Tries to enrich a :class:`~app.model.CompileRequest.Node` according to the specified :class:`~app.enricher.Constraints`.
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
        Throws :class:`ExceptionGroup` containing the exceptions from all :class:`~app.enricher.EnricherStrategy`.

        :param node: The node to enrich.
        :param constraints: Constraints to follow during enrichment.
        :return: Enriched node.

        :raises ExceptionGroup: If no strategy could generate an implementation.
        """

        if isinstance(node, ImplementationNode):
            return node

        results: list[EnrichmentResult] = []
        exceptions: list[Exception] = []

        async for result in asyncio.as_completed(
            x.enrich(node, constraints) for x in self.strategies
        ):
            try:
                results.extend(await result)
            except Exception as ex:
                exceptions.append(ex)

        if len(results) == 0:
            if len(exceptions) == 0:
                raise Exception(f"No implementations were found for node '{node.id}'")

            raise ExceptionGroup(f"Enrichment for node '{node.id}' failed", exceptions)

        key_selector: Callable[[EnrichmentResult], tuple[int | float, int | float]]
        if constraints and constraints.optimizeDepth and not constraints.optimizeWidth:
            key_selector = lambda r: (  # noqa: E731 Do not assign a `lambda` expression, use a `def`
                not_none_or(r.meta_data.depth, math.inf),
                not_none_or(r.meta_data.width, math.inf),
            )
        else:
            key_selector = lambda r: (  # noqa: E731 Do not assign a `lambda` expression, use a `def`
                not_none_or(r.meta_data.width, math.inf),
                not_none_or(r.meta_data.depth, math.inf),
            )

        results = sorted(results, key=key_selector)
        return results[0].enriched_node

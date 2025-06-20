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
from typing import Literal

from openqasm3.ast import Program
from sqlalchemy.ext.asyncio import AsyncSession

from app.enricher.exceptions import (
    EnrichmentFailed,
    NoImplementationFound,
    UnableToInsertImplementation,
)
from app.model.CompileRequest import BaseNode, ImplementationNode, SingleInsertMetaData
from app.model.CompileRequest import (
    Node as FrontendNode,
)
from app.model.data_types import LeqoSupportedType
from app.utils import not_none_or


class ParsedImplementationNode(BaseNode):
    """
    Special node that holds just a parsed implementation.
    """

    type: Literal["parsed-implementation"] = "parsed-implementation"
    implementation: Program


@dataclass(frozen=True)
class Constraints:
    """
    Constraints to follow during enrichment.

    :param requested_inputs: Dictionary where the key is the input index and value the type of the node.
    :param optimizeWidth: If the width of the implementation should be optimized.
    :param optimizeDepth: If the depth of the implementation should be optimized.
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

    enriched_node: ImplementationNode | ParsedImplementationNode
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

        raise RuntimeError("Invalid enrichment result")

    async def insert_enrichment(
        self,
        node: FrontendNode,  # noqa ARG002
        implementation: str,  # noqa ARG002
        requested_inputs: dict[int, LeqoSupportedType],  # noqa ARG002
        meta_data: SingleInsertMetaData,  # noqa ARG002
        session: AsyncSession | None = None,  # noqa ARG002
    ) -> bool:
        """
        Insert an enrichment :class:`~app.model.CompileRequest.ImplementationNode` for a given :class:`~app.model.CompileRequest.Node`.

        :param node: The node to insert the enrichment for.
        :param implementation: The implementation to insert
        :param requested_inputs: The (parsed) requested inputs for that node.
        :param meta_data: meta data for that node
        :param session: The optional database session to use

        :return: Whether the insert was successful.
        """
        return False


class Enricher:
    """
    Handles multiple :class:`~app.enricher.EnricherStrategy`.
    """

    strategies: list[EnricherStrategy]

    def __init__(self, *strategies: EnricherStrategy):
        self.strategies = list(strategies)

    async def try_enrich(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> ImplementationNode | ParsedImplementationNode | None:
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
        self,
        node: FrontendNode | ParsedImplementationNode,
        constraints: Constraints | None,
    ) -> ImplementationNode | ParsedImplementationNode:
        """
        Enrich the given :class:`~app.model.CompileRequest.Node` according to the specified :class:`~app.enricher.Constraints`.
        Throws ExceptionGroup containing the exceptions from all :class:`~app.enricher.EnricherStrategy`.

        :param node: The node to enrich.
        :param constraints: Constraints to follow during enrichment.
        :return: Enriched node.

        :raises ExceptionGroup: If no strategy could generate an implementation.
        """

        if isinstance(node, ImplementationNode | ParsedImplementationNode):
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
                raise NoImplementationFound(node)

            raise EnrichmentFailed(node, exceptions)

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

    async def insert_enrichment(
        self,
        node: FrontendNode,
        implementation: str,
        requested_inputs: dict[int, LeqoSupportedType],
        meta_data: SingleInsertMetaData,
        session: AsyncSession | None = None,
    ) -> None:
        """
        Insert the enrichment :class:`~app.model.CompileRequest.ImplementationNode` for the given :class:`~app.model.CompileRequest.Node`.

        :param node: The node to insert the enrichment for.
        :param implementation: The implementation to insert
        :param requested_inputs: The (parsed) requested inputs for that node.
        :param meta_data: meta data for that node
        :param session: The optional database session to use
        """
        if isinstance(node, ImplementationNode):
            raise UnableToInsertImplementation(node)

        success = False
        exceptions: list[Exception] = []

        async for result in asyncio.as_completed(
            strategy.insert_enrichment(
                node, implementation, requested_inputs, meta_data, session
            )
            for strategy in self.strategies
        ):
            try:
                success = success or await result
            except Exception as ex:
                exceptions.append(ex)

        if not success:
            if len(exceptions) > 1:
                raise ExceptionGroup(
                    "Insertion failed with some exceptions.", exceptions
                )

            raise UnableToInsertImplementation(node)

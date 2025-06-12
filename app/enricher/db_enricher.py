"""
Common baseclass for all enricher strategies that access a database.
"""

from abc import ABC, abstractmethod
from typing import override

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.enricher import (
    Constraints,
    EnricherStrategy,
    EnrichmentResult,
    ImplementationMetaData,
    NodeUnsupportedException,
)
from app.enricher.models import BaseNode
from app.exceptions import InternalServerError
from app.model.CompileRequest import ImplementationNode
from app.model.CompileRequest import Node as FrontendNode


class DataBaseEnricherStrategy(EnricherStrategy, ABC):
    """
    Baseclass for all database enrichers.
    """

    engine: AsyncEngine

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    @abstractmethod
    def _generate_query(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> Select[tuple[BaseNode]] | None:
        raise InternalServerError("Not implemented", node=node.id)

    @override
    async def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> list[EnrichmentResult]:
        query = self._generate_query(node, constraints)
        if query is None:
            return []

        async with AsyncSession(self.engine) as session:
            result_nodes = (await session.execute(query)).scalars().all()

        if not result_nodes:
            return []

        enrichment_results = []
        for result_node in result_nodes:
            if result_node.implementation is None:
                raise NodeUnsupportedException(node)

            enrichment_results.append(
                EnrichmentResult(
                    ImplementationNode(
                        id=node.id, implementation=result_node.implementation
                    ),
                    ImplementationMetaData(
                        width=result_node.width, depth=result_node.depth
                    ),
                )
            )

        return enrichment_results

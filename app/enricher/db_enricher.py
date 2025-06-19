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
)
from app.enricher.exceptions import NoImplementationFound
from app.enricher.models import BaseNode
from app.model.CompileRequest import ImplementationNode, SingleInsertMetaData
from app.model.CompileRequest import Node as FrontendNode
from app.model.data_types import LeqoSupportedType


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
        raise Exception("Not implemented")

    @abstractmethod
    def _generate_database_node(
        self,
        node: FrontendNode,
        implementation: str,
        requested_inputs: dict[int, LeqoSupportedType],
        width: int,
        depth: int | None,
    ) -> BaseNode | None:
        """
        Generate an :class:`~app.enricher.models.BaseNode` which can then be inserted into the database.

        :param node: The frontend node.
        :param implementation: The implementation of the node.
        :param requested_inputs: Dictionary where the key is the input index and value the type of the node.
        :param width: Width of the node implementation.
        :param depth: Depth of the node implementation.
        :return: Whether the insert was successful.
        """
        return None

    @override
    async def insert_enrichment(
        self,
        node: FrontendNode,
        implementation: str,
        requested_inputs: dict[int, LeqoSupportedType],
        meta_data: SingleInsertMetaData,
        session: AsyncSession | None = None,
    ) -> bool:
        assert meta_data.width is not None, "can't happen, this is parsed"
        database_node = self._generate_database_node(
            node, implementation, requested_inputs, meta_data.width, meta_data.depth
        )
        if database_node is None:
            return False

        if session is None:
            async with AsyncSession(self.engine) as session:
                session.add(database_node)
                await session.commit()
                return True

        session.add(database_node)
        return True

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
                raise NoImplementationFound(node)

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

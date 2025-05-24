"""
Contains services that are available via fastapi dependency injection.
"""

import os
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID, uuid4

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.params import Depends
from sqlalchemy.engine.url import URL as DataBaseURL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
)

from app.enricher import Enricher
from app.enricher.encode_value import EncodeValueEnricherStrategy
from app.enricher.gates import GateEnricherStrategy
from app.enricher.literals import LiteralEnricherStrategy
from app.enricher.measure import MeasurementEnricherStrategy
from app.enricher.merger import MergerEnricherStrategy
from app.enricher.models import Base
from app.enricher.operator import OperatorEnricherStrategy
from app.enricher.prepare_state import PrepareStateEnricherStrategy
from app.enricher.splitter import SplitterEnricherStrategy
from app.utils import not_none


@asynccontextmanager
async def use_leqo_db() -> AsyncGenerator[AsyncEngine]:
    """
    Context manager that initializes the leqo database.
    """

    load_dotenv()

    url = DataBaseURL.create(
        drivername=os.environ["SQLALCHEMY_DRIVER"],
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        database=os.environ["POSTGRES_DB"],
    )
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        yield engine
    finally:
        await engine.dispose()


engine_singleton: AsyncEngine | None = None


@asynccontextmanager
async def leqo_lifespan(_app: FastAPI | None = None) -> AsyncGenerator[None]:
    """
    Fastapi lifespan context manager.
    Initializes the database.
    """

    global engine_singleton  # noqa PLW0603

    async with use_leqo_db() as engine:
        engine_singleton = engine
        yield


def get_db_engine() -> AsyncEngine:
    """
    Gets the leqo database.
    Only available when called during leqo_lifespan.
    """

    return not_none(engine_singleton, "DataBase not initialized")


def get_enricher(engine: Annotated[AsyncEngine, Depends(get_db_engine)]) -> Enricher:
    return Enricher(
        LiteralEnricherStrategy(),
        MeasurementEnricherStrategy(),
        SplitterEnricherStrategy(),
        MergerEnricherStrategy(),
        EncodeValueEnricherStrategy(engine),
        PrepareStateEnricherStrategy(engine),
        OperatorEnricherStrategy(engine),
        GateEnricherStrategy(),
    )


NodeIdFactory = Callable[[str], UUID]


def get_node_id_factory() -> NodeIdFactory:
    def node_id_factory(_node_id: str) -> UUID:
        return uuid4()

    return node_id_factory

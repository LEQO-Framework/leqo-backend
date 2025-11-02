"""
Contains services that are available via fastapi dependency injection.
"""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.params import Depends
from sqlalchemy.engine.url import URL as DataBaseURL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
)

from app.config import Settings
from app.db_migrations import apply_migrations
from app.enricher import Enricher
from app.enricher.encode_value import EncodeValueEnricherStrategy
from app.enricher.gates import GateEnricherStrategy
from app.enricher.literals import LiteralEnricherStrategy
from app.enricher.measure import MeasurementEnricherStrategy
from app.enricher.merger import MergerEnricherStrategy
from app.enricher.models import Base as EnricherBase
from app.enricher.operator import OperatorEnricherStrategy
from app.enricher.prepare_state import PrepareStateEnricherStrategy
from app.enricher.qiskit_prepare import HAS_QISKIT, QiskitPrepareStateEnricherStrategy
from app.enricher.splitter import SplitterEnricherStrategy
from app.enricher.workflow import WorkflowEnricherStrategy
from app.model.database_model import Base
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
            await conn.run_sync(EnricherBase.metadata.create_all)
            await apply_migrations(conn)
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
    strategies = [
        LiteralEnricherStrategy(),
        MeasurementEnricherStrategy(),
        SplitterEnricherStrategy(),
        MergerEnricherStrategy(),
        EncodeValueEnricherStrategy(engine),
        PrepareStateEnricherStrategy(engine),
    ]
    if HAS_QISKIT:
        strategies.append(QiskitPrepareStateEnricherStrategy())
    strategies.extend(
        [
            OperatorEnricherStrategy(engine),
            GateEnricherStrategy(),
        ]
    )
    return Enricher(*strategies)


@lru_cache
def get_settings() -> Settings:
    """
    Get environment variables from pydantic and cache them.
    """

    return Settings()


def get_result_url(
    uuid: UUID, settings: Annotated[Settings, Depends(get_settings)]
) -> str:
    """
    Return the full URL for a result identified by its UUID.
    """

    return f"{settings.api_base_url}results/{uuid}"


def get_request_url(
    uuid: UUID, settings: Annotated[Settings, Depends(get_settings)]
) -> str:
    """
    Return the full URL for a stored compile request identified by its UUID.
    """

    return f"{settings.api_base_url}request/{uuid}"


def get_qrms_url(
    uuid: UUID, settings: Annotated[Settings, Depends(get_settings)]
) -> str:
    """
    Return the full URL for the Quantum Resource Models of a request.
    """

    return f"{settings.api_base_url}qrms/{uuid}"


def get_service_deployment_models_url(
    uuid: UUID, settings: Annotated[Settings, Depends(get_settings)]
) -> str:
    """
    Return the full URL for the Service Deployment Models of a request.
    """

    return f"{settings.api_base_url}service-deployment-models/{uuid}"

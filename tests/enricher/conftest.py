import asyncio
import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from testcontainers.postgres import PostgresContainer

from app.enricher.engine import DatabaseEngine
from app.enricher.models import Base

postgres = PostgresContainer("postgres:16-alpine3.20")


@pytest_asyncio.fixture(scope="session", autouse=True)
def engine():
    """Set up the database container for the tests."""

    postgres.start()

    os.environ["POSTGRES_HOST"] = postgres.get_container_host_ip()
    os.environ["POSTGRES_PORT"] = postgres.get_exposed_port(5432)
    os.environ["POSTGRES_USER"] = postgres.username
    os.environ["POSTGRES_PASSWORD"] = postgres.password
    os.environ["POSTGRES_DB"] = postgres.dbname
    os.environ["SQLALCHEMY_DRIVER"] = "postgresql+psycopg"

    engine = DatabaseEngine()
    yield engine

    if engine._engine is None:
        raise RuntimeError("Database engine is not initialized.")

    asyncio.run(reset_database(engine=engine._engine))
    postgres.stop()


@pytest_asyncio.fixture(autouse=True)
async def session(engine: DatabaseEngine) -> AsyncGenerator[AsyncSession]:
    """Create and return a database session."""

    session = engine.get_database_session()
    async with session:
        yield session


async def reset_database(engine: AsyncEngine) -> None:
    """Reset the database by dropping all tables and recreating them."""
    try:
        await engine.dispose()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        raise RuntimeError(f"Failed to reset the database: {e}") from e

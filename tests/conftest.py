import asyncio
import os
import sys
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from testcontainers.postgres import PostgresContainer

from app.services import use_leqo_db

postgres = PostgresContainer("postgres:16-alpine3.20")


@pytest.fixture(scope="session")
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    """
    Ensure we use the old `WindowsSelectorEventLoopPolicy` on windows
    as the postgresql driver cannot work with the modern `ProactorEventLoop`.
    """

    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@pytest_asyncio.fixture(scope="session", autouse=True, loop_scope="session")
async def engine() -> AsyncGenerator[AsyncEngine]:
    """Set up the database container for the tests."""

    postgres.start()

    os.environ["POSTGRES_HOST"] = postgres.get_container_host_ip()
    os.environ["POSTGRES_PORT"] = str(postgres.get_exposed_port(5432))
    os.environ["POSTGRES_USER"] = postgres.username
    os.environ["POSTGRES_PASSWORD"] = postgres.password
    os.environ["POSTGRES_DB"] = postgres.dbname
    os.environ["SQLALCHEMY_DRIVER"] = "postgresql+psycopg"

    async with use_leqo_db() as engine:
        if engine is None:
            raise RuntimeError("Database engine is not initialized.")

        yield engine

    await engine.dispose()

    postgres.stop()


@pytest_asyncio.fixture(autouse=True)
async def session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """Create and return a database session."""

    async with AsyncSession(engine) as session:
        yield session

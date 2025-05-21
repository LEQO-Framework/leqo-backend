import os
from collections.abc import Generator

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from app.enricher.engine import DatabaseEngine
from app.enricher.models import Base

postgres = PostgresContainer("postgres:16-alpine3.20")


@pytest.fixture(scope="session", autouse=True)
def engine() -> Generator[DatabaseEngine]:
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

    reset_database(engine=engine._engine)
    postgres.stop()


@pytest.fixture(scope="session", autouse=True)
def session(engine: DatabaseEngine) -> Generator[Session]:
    """Create and return a database session."""
    try:
        session = engine.get_database_session()
        yield session
        session.close()
    except Exception as e:
        raise RuntimeError(f"Failed to create database session: {e}") from e
    

def reset_database(engine: Engine) -> None:
        """Reset the database by dropping all tables and recreating them."""
        
        try:
            Base.metadata.drop_all(engine)
            Base.metadata.create_all(engine)
        except Exception as e:
            raise RuntimeError(f"Failed to reset the database: {e}") from e

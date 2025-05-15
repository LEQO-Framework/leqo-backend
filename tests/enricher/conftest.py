import os
from collections.abc import Generator

import pytest
from sqlalchemy import URL, Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer

from app.enricher.engine import DatabaseEngine

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
    
    engine = DatabaseEngine()
    yield engine
    
    engine._reset_database()
    postgres.stop()

@pytest.fixture(scope="session", autouse=True)
def session(engine: DatabaseEngine) -> Generator[Session]:
    """Create and return a database session."""
    try:
        session = engine._get_database_session()
        yield session
        session.close()
    except Exception as e:
        raise RuntimeError(f"Failed to create database session: {e}") from e

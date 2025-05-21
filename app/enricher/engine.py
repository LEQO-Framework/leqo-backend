"""Creation of the async database engine singleton class to connect and execute operation on the database."""

import asyncio
import os

from dotenv import load_dotenv
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.enricher.models import Base

load_dotenv()


class DatabaseEngine:
    """Singleton class to manage the async database engine."""

    _instance = None
    _engine = None

    def __new__(cls) -> "DatabaseEngine":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize_engine()
        return cls._instance

    def _initialize_engine(self) -> None:
        """Initialize the async database engine."""
        try:
            url = URL.create(
                drivername=os.environ["SQLALCHEMY_DRIVER"],
                username=os.environ["POSTGRES_USER"],
                password=os.environ["POSTGRES_PASSWORD"],
                host=os.environ["POSTGRES_HOST"],
                port=int(os.environ["POSTGRES_PORT"]),
                database=os.environ["POSTGRES_DB"],
            )
            self._engine = create_async_engine(url)

            asyncio.run(self.async_create_all())
        except KeyError as e:
            raise RuntimeError(f"Missing required environment variable: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to create the database engine: {e}") from e

    async def async_create_all(self) -> None:
        """Create all tables in the database."""
        if self._engine is None:
            raise RuntimeError("Database engine has not been initialized.")

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    def get_database_session(self) -> AsyncSession:
        """Create and return a async database session.

        :return Session: A async database session to commit things to the database
        """
        try:
            return AsyncSession(self._engine)
        except Exception as e:
            raise RuntimeError(f"Failed to create database session: {e}") from e

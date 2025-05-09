import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.enricher.models import Base

load_dotenv()


class DatabaseEngine:
    """Singleton class to manage the database engine."""

    _instance = None
    _engine = None

    def __new__(cls) -> "DatabaseEngine":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize_engine()
        return cls._instance

    def _initialize_engine(self) -> None:
        """Initialize the database engine."""
        try:
            url = URL.create(
                drivername=os.environ["SQLALCHEMY_DRIVER"],
                username=os.environ["POSTGRES_USER"],
                password=os.environ["POSTGRES_PASSWORD"],
                host=os.environ["POSTGRES_HOST"],
                port=int(os.environ["POSTGRES_PORT"]),
                database=os.environ["POSTGRES_DB"],
            )
            self._engine = create_engine(url)
            Base.metadata.create_all(self._engine)
        except KeyError as e:
            raise RuntimeError(f"Missing required environment variable: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to create the database engine: {e}") from e
        
    def _get_database_session(self) -> Session:
        """Create and return a database session.
        
        :return Session: A database session to commit things to the database
        """
        try:
            Session = sessionmaker(bind=self._engine)
            return Session()
        except Exception as e:
            raise RuntimeError(f"Failed to create database session: {e}") from e

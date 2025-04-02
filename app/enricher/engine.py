import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from app.enricher.utils import reset_database

load_dotenv()

try:
    url = URL.create(
        drivername=os.environ['SQLALCHEMY_DRIVER'],
        username=os.environ['POSTGRES_USER'],
        password=os.environ['POSTGRES_PASSWORD'],
        host=os.environ['POSTGRES_HOST'],
        port=os.environ['POSTGRES_PORT'],
        database=os.environ['POSTGRES_DB']
    )
    engine = create_engine(url, echo=True)
    reset_database(engine)
except KeyError as e:
    raise RuntimeError(f"Missing required environment variable: {e}")
except Exception as e:
    raise RuntimeError(f"Failed to create the database engine: {e}")

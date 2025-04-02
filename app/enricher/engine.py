import os
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from dotenv import load_dotenv
from app.enricher.utils import create_database

load_dotenv()

try:
    url = URL.create(
        drivername="postgresql+psycopg",
        host="172.18.0.3",
        port=os.environ['POSTGRES_PORT'],
        username=os.environ['POSTGRES_USER'],
        password=os.environ['POSTGRES_PASSWORD'],
        database=os.environ['POSTGRES_DB']
    )
    engine = create_engine(url, echo=True)
    create_database(engine)
except KeyError as e:
    raise RuntimeError(f"Missing required environment variable: {e}")
except Exception as e:
    raise RuntimeError(f"Failed to create the database engine: {e}")

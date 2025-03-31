import os
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from dotenv import load_dotenv

load_dotenv()

url = URL.create(
    drivername="postgresql+psycopg",
    host="postgres",
    port=os.environ['POSTGRES_PORT'],
    username=os.environ['POSTGRES_USER'],
    password=os.environ['POSTGRES_PASSWORD'],
    database=os.environ['POSTGRES_DB']
)

engine = create_engine(url)

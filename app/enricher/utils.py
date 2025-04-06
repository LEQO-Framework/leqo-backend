from sqlalchemy import Engine

from app.enricher.models import Base


def create_database(engine: Engine) -> None:
    Base.metadata.create_all(engine)

def drop_database(engine: Engine) -> None:
    Base.metadata.drop_all(engine)

def reset_database(engine: Engine) -> None:
    drop_database(engine)
    create_database(engine)

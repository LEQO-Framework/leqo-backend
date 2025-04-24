# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# This file is only meant for testing purposes
# Delete this file after the review
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

from sqlalchemy import Column, Integer, Text, select
from sqlalchemy.orm import sessionmaker

from app.enricher.engine import DatabaseEngine
from app.enricher.models import Base


class QuasmImplementation(Base):
    """Used as a definition to create a table in the DB
    Normally in ./models but moved here for simplicity."""

    __tablename__ = "qasm_impl"

    id = Column(Integer(), primary_key=True)
    quasm = Column(Text, nullable=False)


# Used to connect to the DB through the engine
databaseEngine = DatabaseEngine()
Session = sessionmaker(bind=databaseEngine._engine)
session = Session()


def createQuasmImplementation(quasm: str) -> None:
    with Session() as session:
        qasmImplementation = QuasmImplementation(quasm=quasm)
        session.add(qasmImplementation)
        session.commit()


def findQuasmImplementation(searchTerm: str) -> list[tuple[int, str]]:
    with Session() as session:
        query = select(QuasmImplementation).where(
            QuasmImplementation.quasm == searchTerm
        )
        result = session.execute(query)
        return [(row[0].id, row[0].quasm) for row in result.all()]


def demo() -> list[tuple[int, str]]:
    createQuasmImplementation("x q[0]")
    createQuasmImplementation("cx q[1], q[2]")
    createQuasmImplementation("c[0] = measure q[2]")
    return findQuasmImplementation("x q[0]")

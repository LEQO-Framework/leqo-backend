# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# This file is only meant for testing purposes
# Delete this file after the review
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

from sqlalchemy import Column, Integer, Text
from app.enricher.models import Base
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.enricher.engine import engine
from app.enricher.utils import reset_database

class QuasmImplementation(Base):
    __tablename__ = 'qasm_impl'

    id = Column(Integer(), primary_key=True)
    quasm = Column(Text, nullable=False)

Session = sessionmaker(bind=engine)
session = Session()

def createQuasmImplementation(quasm: str) -> None:
    with Session() as session:
        qasmImplementation = QuasmImplementation(quasm=quasm)
        session.add(qasmImplementation)
        session.commit()

def findQuasmImplementation(searchTerm: str) -> None:
    with Session() as session:
        query = select(QuasmImplementation).where(QuasmImplementation.quasm == searchTerm)
        result = session.execute(query)
        return [(row[0].id, row[0].quasm) for row in result.all()]

def demo() -> list[tuple]:
    reset_database(engine)
    createQuasmImplementation("x q[0]")
    createQuasmImplementation("cx q[1], q[2]")
    createQuasmImplementation("c[0] = measure q[2]")
    return findQuasmImplementation("x q[0]")

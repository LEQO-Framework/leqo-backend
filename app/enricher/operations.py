from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from app.enricher import engine
from app.enricher.models import QuasmImplementation

Session = sessionmaker(bind=engine)
session = Session()

def createQuasmImplementation(quasm: str) -> None:
    with Session(engine) as session:
        qasmImplementation = QuasmImplementation(quasm=quasm)
        session.add(qasmImplementation)
        session.commit()

def updateQuasmImplementation(quasmImplementation: QuasmImplementation, quasm: str) -> None:
    with Session(engine) as session:
        quasmImplementation.quasm = quasm
        session.add(quasmImplementation)
        session.commit()

def findQuasmImplementation(searchTerm: str) -> None:
    with Session(engine) as session:
        query = select(QuasmImplementation).where(QuasmImplementation.quasm == searchTerm)
        result = session.execute(query)
        print(result.all())

def deleteQuasmImplementation(quasmImplementation: QuasmImplementation) -> None:
    with Session(engine) as session:
        session.delete(quasmImplementation)
        session.commit()

def populateQuasmImplementation() -> None:
    createQuasmImplementation("x q[0]")
    createQuasmImplementation("cx q[1], q[2]")
    createQuasmImplementation("c[0] = measure q[2]")

populateQuasmImplementation()
findQuasmImplementation("x q[0]")

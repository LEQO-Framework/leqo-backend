import os
from sqlalchemy import create_engine, Column, Integer, Text
from sqlalchemy.engine import URL
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

url = URL.create(
    drivername="postgressql",
    username=os.environ['POSTGRES_USER'],
    password=os.environ['POSTGRES_PASSWORD'],
    database=os.environ['POSTGRES_DB'],
    host="postgres",
    port=os.environ['POSTGRES_PORT']
)

engine = create_engine(url)
connection = engine.connect()

Base = declarative_base()

class QasmSnippets(Base):
    __tablename__ = 'qasm_snippets'

    id = Column(Integer(), primary_key=True)
    qasm = Column(Text, nullable=False)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

qasmSnippet1 = QasmSnippets(qasm="x q[0]")
qasmSnippet2 = QasmSnippets(qasm="cx q[1], q[2]")
qasmSnippet3 = QasmSnippets(qasm="c[0] = measure q[2]")

session.add_all([qasmSnippet1, qasmSnippet2, qasmSnippet3])
session.commit()

print(session.query(QasmSnippets).where(QasmSnippets.qasm == "x q[0]"))

from sqlalchemy import Column, Integer, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class QuasmImplementation(Base):
    __tablename__ = 'qasm_impl'

    id = Column(Integer(), primary_key=True)
    quasm = Column(Text, nullable=False)

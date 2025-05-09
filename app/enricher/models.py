import enum
from typing import ClassVar

from sqlalchemy import Column, Enum, ForeignKey, Integer, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class NodeType(enum.Enum):
    ENCODE = "encode"
    PREPARE = "prepare"
    OPERATOR = "operator"


class EncodingType(enum.Enum):
    AMPLITUDE = "amplitude"
    ANGLE = "angle"
    BASIS = "basis"
    CUSTOM = "custom"
    MATRIX = "matrix"
    SCHMIDT = "schmidt"


class QuantumStateType(enum.Enum):
    PHI_PLUS = "ϕ+"
    PHI_MINUS = "ϕ-"
    PSI_PLUS = "ψ+"
    PSI_MINUS = "ψ-"
    CUSTOM = "custom"
    GHZ = "ghz"
    UNIFORM = "uniform"
    W = "w"


class OperatorType(enum.Enum):
    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"
    POW = "**"
    OR = "|"
    AND = "&"
    NOT = "~"
    XOR = "^"
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    EQ = "=="
    NEQ = "!="
    MIN = "min"
    MAX = "max"
    SEARCH = "search"


class InputType(enum.Enum):
    IntType = "IntType"
    FloatType = "FloatType"
    BitType = "BitType"
    BoolType = "BoolType"
    QubitType = "QubitType"


class QuantumNode(Base):
    __tablename__ = "quantum_nodes"

    id = Column(Integer, primary_key=True)
    type = Column(Enum(NodeType), nullable=False)
    depth = Column(Integer, nullable=False)
    width = Column(Integer, nullable=False)
    implementation = Column(Text)
    uncompute_implementation = Column(Text)
    inputs = Column(Enum(InputType), nullable=False)

    __mapper_args__: ClassVar[dict] = {
        "polymorphic_on": type,
        "polymorphic_identity": "quantum_node",
    }


class EncodeNode(QuantumNode):
    __tablename__ = "encode_nodes"

    id = Column(Integer, ForeignKey("quantum_nodes.id"), primary_key=True)
    encoding = Column(Enum(EncodingType), nullable=False)
    bounds = Column(Integer, nullable=False)

    __mapper_args__: ClassVar[dict[str, NodeType]] = {"polymorphic_identity": NodeType.ENCODE}


class PrepareNode(QuantumNode):
    __tablename__ = "prepare_nodes"

    id = Column(Integer, ForeignKey("quantum_nodes.id"), primary_key=True)
    size = Column(Integer, nullable=False)
    quantum_state = Column(Enum(QuantumStateType), nullable=False)

    __mapper_args__: ClassVar[dict[str, NodeType]] = {"polymorphic_identity": NodeType.PREPARE}


class OperatorNode(QuantumNode):
    __tablename__ = "operator_nodes"

    id = Column(Integer, ForeignKey("quantum_nodes.id"), primary_key=True)
    operator = Column(Enum(OperatorType), nullable=False)

    __mapper_args__: ClassVar[dict[str, NodeType]] = {"polymorphic_identity": NodeType.OPERATOR}

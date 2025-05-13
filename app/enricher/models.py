"""Database schema to store and query node implementations."""

import enum
from typing import ClassVar

from sqlalchemy import Column, Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class NodeType(enum.Enum):
    ENCODE = "encode"
    PREPARE = "prepare"
    OPERATOR = "operator"


class EncodingType(enum.Enum):
    AMPLITUDE = "amplitude"
    ANGLE = "angle"
    BASIS = "basis"
    MATRIX = "matrix"
    SCHMIDT = "schmidt"


class QuantumStateType(enum.Enum):
    PHI_PLUS = "ϕ+"
    PHI_MINUS = "ϕ-"
    PSI_PLUS = "ψ+"
    PSI_MINUS = "ψ-"
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


class BaseNode(Base):
    """Base class for all nodes.

    :param id: ID and primary key of a node
    :param type: One of the types defined in :class:`NodeType`
    :param depth: Depth of the node implementation
    :param width: Width of the node implementation
    :param implementation: Implementation of the node
    :param inputs: An array JSON object of the following form:
                   [
                       {
                           index: int,
                           type: `class:InputType`,
                           size: int | None
                       }    
                   ]
                   If there are no inputs this should be an empty array.
    """

    __tablename__ = "quantum_nodes"

    id = Column(Integer, primary_key=True)
    type = Column(Enum(NodeType), nullable=False)
    depth = Column(Integer, nullable=False)
    width = Column(Integer, nullable=False)
    implementation = Column(Text, nullable=False)
    inputs = Column(JSONB, nullable=False)

    __mapper_args__: ClassVar[dict] = {
        "polymorphic_on": type,
        "polymorphic_identity": "quantum_node",
    }


class EncodeValueNode(BaseNode):
    """Special properties of EncodeValueNode.

    :param id: Foreign key to the id of the BaseNode (:class:`BaseNode`)
    :param encoding: Type of encoding defined by :class:`EncodingType`
    :param bounds: ???????????
    """

    __tablename__ = "encode_nodes"

    id = Column(Integer, ForeignKey("quantum_nodes.id"), primary_key=True)
    encoding = Column(Enum(EncodingType), nullable=False)
    bounds = Column(Integer, nullable=False)

    __mapper_args__: ClassVar[dict[str, NodeType]] = {
        "polymorphic_identity": NodeType.ENCODE
    }


class PrepareStateNode(BaseNode):
    """Special properties of PrepareStateNode

    :param id: Foreign key to the id of the BaseNode (:class:`BaseNode`)
    :param size: Integer value for the size the implementation supports
    :param quantum_state: Quantum state of the implementation defined by :class:`QuantumStateType`
    """

    __tablename__ = "prepare_nodes"

    id = Column(Integer, ForeignKey("quantum_nodes.id"), primary_key=True)
    size = Column(Integer, nullable=False)
    quantum_state = Column(Enum(QuantumStateType), nullable=False)

    __mapper_args__: ClassVar[dict[str, NodeType]] = {
        "polymorphic_identity": NodeType.PREPARE
    }


class OperatorNode(BaseNode):
    """Special properties of OperatorNode

    :param: id: Foreign key to the id of the BaseNode (:class:`BaseNode`)
    :param: operator: Operator the implementation supports
    """

    __tablename__ = "operator_nodes"

    id = Column(Integer, ForeignKey("quantum_nodes.id"), primary_key=True)
    operator = Column(Enum(OperatorType), nullable=False)

    __mapper_args__: ClassVar[dict[str, NodeType]] = {
        "polymorphic_identity": NodeType.OPERATOR
    }

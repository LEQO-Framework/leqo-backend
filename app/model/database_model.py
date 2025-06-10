"""Database schema for everything stored in the database."""

import enum
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.model.StatusResponse import StatusType


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


class InputType(enum.Enum):
    IntType = "IntType"
    FloatType = "FloatType"
    BitType = "BitType"
    BoolType = "BoolType"
    QubitType = "QubitType"


class Base(DeclarativeBase):
    pass


class ProcessStates(Base):
    """Class to store the states of all current processes
    which await processing or a currently processed.
    """

    __tablename__ = "process_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[StatusType] = mapped_column(nullable=False)
    createdAt: Mapped[datetime] = mapped_column(nullable=True)
    completedAt: Mapped[datetime] = mapped_column(nullable=True)
    progressPercentage: Mapped[int] = mapped_column(nullable=True)
    progressCurrentStep: Mapped[str] = mapped_column(nullable=True)
    result: Mapped[str] = mapped_column(nullable=True)


class ProcessedResults(Base):
    """Class to store the processed results."""

    __tablename__ = "processed_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    results: Mapped[list["ResultImplementation"]] = relationship(
        "ResultImplementation",
        back_populates="processed_result",
        cascade="all, delete-orphan",
    )


class ResultImplementation(Base):
    """Class to store resulting implementations."""

    __tablename__ = "result_implementations"

    id: Mapped[int] = mapped_column(primary_key=True)
    implementation: Mapped[str] = mapped_column(nullable=False)
    processed_result_id: Mapped[int] = mapped_column(
        ForeignKey("processed_results.id"), nullable=False
    )

    processed_result: Mapped["ProcessedResults"] = relationship(
        "ProcessedResults", back_populates="results"
    )


class BaseNode(Base):
    """Base class for all nodes.

    :param id: ID and primary key of a node
    :param type: One of the types defined in :class:`NodeType`
    :param depth: Depth of the node implementation
    :param width: Width of the node implementation
    :param implementation: Implementation of the node
    :param inputs: 1-n-Relationship with :class:`Input`
    """

    __tablename__ = "base_nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[NodeType] = mapped_column(Enum(NodeType), nullable=False)
    depth: Mapped[int] = mapped_column(nullable=False)
    width: Mapped[int] = mapped_column(nullable=False)
    implementation: Mapped[str] = mapped_column(Text, nullable=False)

    inputs: Mapped[list["Input"]] = relationship(
        "Input", back_populates="node", cascade="all, delete-orphan"
    )

    __mapper_args__ = {  # noqa: RUF012, mypy false positive error
        "polymorphic_on": type,
        "polymorphic_identity": "base_nodes",
    }


class Input(Base):
    """Input class to store input information for nodes."""

    __tablename__ = "inputs"

    id: Mapped[int] = mapped_column(primary_key=True)
    index: Mapped[int] = mapped_column(nullable=False)
    type: Mapped[InputType] = mapped_column(Enum(InputType), nullable=False)
    size: Mapped[int | None] = mapped_column(nullable=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("base_nodes.id"), nullable=False)

    node: Mapped[BaseNode] = relationship("BaseNode", back_populates="inputs")


class EncodeValueNode(BaseNode):
    """Special properties of EncodeValueNode.

    :param id: Foreign key to the id of the BaseNode (:class:`BaseNode`)
    :param encoding: Type of encoding defined by :class:`EncodingType`
    :param bounds: Bound of the encode value node
    """

    __tablename__ = "encode_nodes"

    id: Mapped[int] = mapped_column(ForeignKey("base_nodes.id"), primary_key=True)
    encoding: Mapped[EncodingType] = mapped_column(Enum(EncodingType), nullable=False)
    bounds: Mapped[int] = mapped_column(nullable=False)

    __mapper_args__ = {  # noqa: RUF012, mypy false positive error
        "polymorphic_identity": NodeType.ENCODE
    }


class PrepareStateNode(BaseNode):
    """Special properties of PrepareStateNode

    :param id: Foreign key to the id of the BaseNode (:class:`BaseNode`)
    :param size: Integer value for the size the implementation supports
    :param quantum_state: Quantum state of the implementation defined by :class:`QuantumStateType`
    """

    __tablename__ = "prepare_nodes"

    id: Mapped[int] = mapped_column(ForeignKey("base_nodes.id"), primary_key=True)
    quantum_state: Mapped[QuantumStateType] = mapped_column(
        Enum(QuantumStateType), nullable=False
    )
    size: Mapped[int] = mapped_column(nullable=False)

    __mapper_args__ = {  # noqa: RUF012, mypy false positive error
        "polymorphic_identity": NodeType.PREPARE
    }


class OperatorNode(BaseNode):
    """Special properties of OperatorNode

    :param: id: Foreign key to the id of the BaseNode (:class:`BaseNode`)
    :param: operator: Operator the implementation supports
    """

    __tablename__ = "operator_nodes"

    id: Mapped[int] = mapped_column(ForeignKey("base_nodes.id"), primary_key=True)
    operator: Mapped[OperatorType] = mapped_column(Enum(OperatorType), nullable=False)

    __mapper_args__ = {  # noqa: RUF012, mypy false positive error
        "polymorphic_identity": NodeType.OPERATOR
    }

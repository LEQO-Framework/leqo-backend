"""Database schema for the enricher nodes."""

import enum

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class NodeType(enum.Enum):
    """
    Enum for different node types.
    """

    ENCODE = "encode"
    """
    Node for encoding classical data into quantum states.
    """

    PREPARE = "prepare"
    """
    Node for preparing predefined quantum states.
    """

    OPERATOR = "operator"
    """
    Node representing a classical or quantum operator.
    """


class EncodingType(enum.Enum):
    """
    Enum for supported encoding types.
    """

    AMPLITUDE = "amplitude"
    """
    Amplitude encoding of quantum states.
    """

    ANGLE = "angle"
    """
    Angle encoding of quantum states.
    """

    BASIS = "basis"
    """
    Basis state encoding.
    """

    MATRIX = "matrix"
    """
    Matrix-based custom encoding.
    """

    SCHMIDT = "schmidt"
    """
    Schmidt decomposition-based encoding.
    """


class QuantumStateType(enum.Enum):
    """
    Enum for quantum state preparation options.
    """

    PHI_PLUS = "ϕ+"
    """
    Bell state ``|ϕ+⟩``
    """

    PHI_MINUS = "ϕ-"
    """
    Bell state ``|ϕ-⟩``
    """

    PSI_PLUS = "ψ+"
    """
    Bell state ``|ψ+⟩``
    """

    PSI_MINUS = "ψ-"
    """
    Bell state ``|ψ-⟩``
    """

    GHZ = "ghz"
    """
    Greenberger-Horne-Zeilinger state.
    """

    UNIFORM = "uniform"
    """
    Uniform superposition state.
    """

    W = "w"
    """
    W-state.
    """


class OperatorType(enum.Enum):
    """
    Enum for supported classical and quantum operators.
    """

    ADD = "+"
    """
    Addition operator (+).
    """

    SUB = "-"
    """
    Subtraction operator (-).
    """

    MUL = "*"
    """
    Multiplication operator (*).
    """

    DIV = "/"
    """
    Division operator (/).
    """

    POW = "**"
    """
    Exponentiation operator (**).
    """

    OR = "|"
    """
    Bitwise OR (|).
    """

    AND = "&"
    """
    Bitwise AND (&).
    """

    NOT = "~"
    """
    Bitwise NOT (~).
    """

    XOR = "^"
    """
    Bitwise XOR (^).
    """

    LT = "<"
    """
    Less than (<).
    """

    LE = "<="
    """
    Less than or equal to (<=).
    """

    GT = ">"
    """
    Greater than (>).
    """

    GE = ">="
    """
    Greater than or equal to (>=).
    """

    EQ = "=="
    """
    Equality comparison (==).
    """

    NEQ = "!="
    """
    Inequality comparison (!=).
    """

    MIN = "min"
    """
    Minimum of two values.
    """

    MAX = "max"
    """
    Maximum of two values.
    """


class InputType(enum.Enum):
    """
    Enum for types of inputs to node implementations.
    """

    IntType = "IntType"
    """
    Classical integer input.
    """

    FloatType = "FloatType"
    """
    Classical float input.
    """

    BitType = "BitType"
    """
    Classical bit input.
    """

    BoolType = "BoolType"
    """
    Boolean value input.
    """

    QubitType = "QubitType"
    """
    Quantum input (qubit).
    """


class Base(DeclarativeBase):
    """
    SQLAlchemy declarative base class for table definitions.
    """


class BaseNode(Base):
    """
    Base class for all nodes.

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
    depth: Mapped[int] = mapped_column(nullable=True)
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
    """
    Input class to store input information for nodes.

    :param id: Primary key.
    :param index: Input index within the node.
    :param type: Type of the input from :class:`InputType`.
    :param size: Optional size for array-based types.
    :param node_id: Foreign key to the parent node.
    :param node: Back-reference to the parent :class:`BaseNode`.
    """

    __tablename__ = "inputs"

    id: Mapped[int] = mapped_column(primary_key=True)
    index: Mapped[int] = mapped_column(nullable=False)
    type: Mapped[InputType] = mapped_column(Enum(InputType), nullable=False)
    size: Mapped[int | None] = mapped_column(nullable=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("base_nodes.id"), nullable=False)

    node: Mapped[BaseNode] = relationship("BaseNode", back_populates="inputs")


class EncodeValueNode(BaseNode):
    """
    Special properties of EncodeValueNode.

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
    """
    Special properties of PrepareStateNode

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
    """
    Special properties of OperatorNode

    :param: id: Foreign key to the id of the BaseNode (:class:`BaseNode`)
    :param: operator: Operator the implementation supports
    """

    __tablename__ = "operator_nodes"

    id: Mapped[int] = mapped_column(ForeignKey("base_nodes.id"), primary_key=True)
    operator: Mapped[OperatorType] = mapped_column(Enum(OperatorType), nullable=False)

    __mapper_args__ = {  # noqa: RUF012, mypy false positive error
        "polymorphic_identity": NodeType.OPERATOR
    }

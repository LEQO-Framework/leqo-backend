"""
This module defines the data models for compile requests.
It provides classes to model metadata, node data, and the complete compile request.
"""

from __future__ import annotations

from abc import ABC
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.openqasm3.stdgates import (
    OneQubitGate,
    OneQubitGateWithAngle,
    ThreeQubitGate,
    TwoQubitGate,
    TwoQubitGateWithAngle,
    TwoQubitGateWithParam,
)


class OptimizeSettings(ABC):
    """
    Abstract base class providing optimization settings.

    :param int | None optimizeWidth: If set, enables circuit width optimization with a user-defined priority.
    :param int | None optimizeDepth: If set, enables circuit depth optimization with a user-defined priority.
    """

    optimizeWidth: int | None
    optimizeDepth: int | None


class MetaData(BaseModel, OptimizeSettings):
    """
    Contains metadata for a compile request, including versioning and optimization preferences.

    :param str version: Version identifier of the project or model.
    :param str name: Name of the quantum circuit or model.
    :param str description: Human-readable description of the model.
    :param str author: Author of the model.
    :param int | None optimizeWidth: Optimization setting for reducing circuit width (optional).
    :param int | None optimizeDepth: Optimization setting for reducing circuit depth (optional).
    """

    version: str
    name: str
    description: str
    author: str
    optimizeWidth: Annotated[int, Field(gt=0)] | None = None
    optimizeDepth: Annotated[int, Field(gt=0)] | None = None


class BaseNode(BaseModel):
    """
    Abstract base class for all node types used in a compile request.

    :param str id: Unique identifier for the node.
    :param str | None label: Optional label for the node used for display purposes.
    """

    id: str
    label: str | None = None


class ImplementationNode(BaseNode):
    """
    Node containing a user-defined OpenQASM implementation.

    :param Literal["implementation"] type: Constant value indicating this node type.
    :param str implementation: Raw OpenQASM code associated with the node.
    """

    type: Literal["implementation"] = "implementation"
    implementation: str


# region Boundary Nodes
class EncodeValueNode(BaseNode):
    """
    Node representing quantum state encoding from classical values.

    :param Literal["encode"] type: Constant value indicating this node type.
    :param Literal encoding: Encoding scheme used (e.g. "amplitude", "basis", etc.).
    :param int bounds: Indicates whether values are clamped (0 or 1).
    """

    type: Literal["encode"] = "encode"
    encoding: Literal["amplitude", "angle", "basis", "custom", "matrix", "schmidt"]
    bounds: int = Field(ge=0, default=0, le=1)


class PrepareStateNode(BaseNode):
    """
    Node for preparing known quantum states like Bell or GHZ.

    :param Literal["prepare"] type: Constant value indicating this node type.
    :param Literal quantumState: Type of quantum state to prepare (e.g. "ψ+", "ghz").
    :param int size: Number of qubits involved in state preparation.
    """

    type: Literal["prepare"] = "prepare"
    quantumState: Literal["ϕ+", "ϕ-", "ψ+", "ψ-", "custom", "ghz", "uniform", "w"]
    size: int = Field(gt=0)


class SplitterNode(BaseNode):
    """
    Node that splits qubits into multiple branches.

    :param Literal["splitter"] type: Constant value indicating this node type.
    :param int numberOutputs: Number of output branches created.
    """

    type: Literal["splitter"] = "splitter"
    numberOutputs: int = Field(ge=2)


class MergerNode(BaseNode):
    """
    Node that merges multiple input branches into a single stream.

    :param Literal["merger"] type: Constant value indicating this node type.
    :param int numberInputs: Number of input branches merged.
    """

    type: Literal["merger"] = "merger"
    numberInputs: int = Field(ge=2)


class MeasurementNode(BaseNode):
    """
    Node performing quantum measurement on specified qubit indices.

    :param Literal["measure"] type: Constant value indicating this node type.
    :param list[int] indices: List of qubit indices to measure.
    """

    type: Literal["measure"] = "measure"
    indices: list[Annotated[int, Field(ge=0)]]


BoundaryNode = (
    EncodeValueNode | PrepareStateNode | SplitterNode | MergerNode | MeasurementNode
)
# endregion


class QubitNode(BaseNode):
    """
    Node representing qubit allocation.

    :param Literal["qubit"] type: Constant value indicating this node type.
    :param int size: Number of qubits to allocate.
    """

    type: Literal["qubit"] = "qubit"
    size: int = Field(default=1, ge=1)


class GateNode(BaseNode):
    """
    Node representing application of a quantum gate.

    :param Literal["gate"] type: Constant value indicating this node type.
    :param gate: The gate to apply (e.g., "x", "cnot", etc.).
    """

    type: Literal["gate"] = "gate"
    gate: OneQubitGate | TwoQubitGate | ThreeQubitGate | Literal["cnot", "toffoli"]


class ParameterizedGateNode(BaseNode):
    """
    Node representing a gate that requires a parameter (e.g., angle rotation).

    :param Literal["gate-with-param"] type: Constant value indicating this node type.
    :param gate: The parameterized gate to apply.
    :param float parameter: Value of the gate's parameter.
    """

    type: Literal["gate-with-param"] = "gate-with-param"
    gate: OneQubitGateWithAngle | TwoQubitGateWithParam | TwoQubitGateWithAngle
    parameter: float


# region Literals
class BitLiteralNode(BaseNode):
    """
    Node representing a fixed classical bit value (0 or 1).

    :param Literal["bit"] type: Constant value indicating this node type.
    :param Literal[0, 1] value: Bit value.
    """

    type: Literal["bit"] = "bit"
    value: Literal[0, 1]


class BoolLiteralNode(BaseNode):
    """
    Node representing a boolean literal.

    :param Literal["bool"] type: Constant value indicating this node type.
    :param bool value: Boolean value.
    """

    type: Literal["bool"] = "bool"
    value: bool


class IntLiteralNode(BaseNode):
    """
    Node representing an integer literal.

    :param Literal["int"] type: Constant value indicating this node type.
    :param int bitSize: Bit size of the integer.
    :param int value: Integer value.
    """

    type: Literal["int"] = "int"
    bitSize: int = Field(default=32, ge=1)
    value: int


class FloatLiteralNode(BaseNode):
    """
    Node representing a floating-point literal.

    :param Literal["float"] type: Constant value indicating this node type.
    :param int bitSize: Bit size of the float.
    :param float value: Float value.
    """

    type: Literal["float"] = "float"
    bitSize: int = Field(default=32, ge=1)
    value: float


LiteralNode = BitLiteralNode | BoolLiteralNode | IntLiteralNode | FloatLiteralNode
# endregion


class AncillaNode(BaseNode):
    """
    Node allocating ancillary qubits for temporary computation.

    :param Literal["ancilla"] type: Constant value indicating this node type.
    :param int size: Number of ancilla qubits allocated.
    """

    type: Literal["ancilla"] = "ancilla"
    size: int = Field(default=1, ge=1)


# region ControlFlow
class NestedBlock(BaseModel):
    """
    Represents a subgraph or code block used inside control flow nodes.

    :param list[NestableNode] nodes: List of nodes within the block.
    :param list[Edge] edges: Connections between the nodes.
    """

    nodes: list[NestableNode]
    edges: list[Edge]


class IfThenElseNode(BaseNode):
    """
    Node representing conditional execution.

    :param Literal["if-then-else"] type: Constant value indicating this node type.
    :param str condition: Condition expression used to branch execution.
    :param NestedBlock thenBlock: Code block executed if the condition is true.
    :param NestedBlock elseBlock: Code block executed if the condition is false.
    """

    type: Literal["if-then-else"] = "if-then-else"
    condition: str
    thenBlock: NestedBlock
    elseBlock: NestedBlock


class RepeatNode(BaseNode):
    """
    Node representing a repeat loop structure.

    :param Literal["repeat"] type: Constant value indicating this node type.
    :param int iterations: Number of loop iterations.
    :param NestedBlock block: Code block to repeat.
    """

    type: Literal["repeat"] = "repeat"
    iterations: int = Field(gt=0)
    block: NestedBlock


ControlFlowNode = IfThenElseNode | RepeatNode
# endregion


class OperatorNode(BaseNode):
    """
    Node representing a classical operation (arithmetic, bitwise, comparison).

    :param Literal["operator"] type: Constant value indicating this node type.
    :param Literal operator: Type of operator (e.g., "+", "&", "==").
    """

    type: Literal["operator"] = "operator"
    operator: Literal[
        "+",
        "-",
        "*",
        "/",
        "**",
        "|",
        "&",
        "~",
        "^",
        "<",
        "<=",
        ">",
        ">=",
        "==",
        "!=",
        "min",
        "max",
    ]


NestableNode = (
    ImplementationNode
    | BoundaryNode
    | GateNode
    | ParameterizedGateNode
    | LiteralNode
    | AncillaNode
    | OperatorNode
)
Node = NestableNode | QubitNode | ControlFlowNode


class Edge(BaseModel):
    """
    Represents a connection between two ports of nodes.

    :param tuple[str, int] source: Tuple of (node_id, output_index).
    :param tuple[str, int] target: Tuple of (node_id, input_index).
    :param int | None size: Optional size override for the edge.
    :param str | None identifier: Optional name or alias of the connection.
    """

    source: tuple[str, Annotated[int, Field(ge=0)]]
    target: tuple[str, Annotated[int, Field(ge=0)]]
    size: int | None = None
    identifier: str | None = None


class CompileRequest(BaseModel):
    """
    Top-level object representing a full graph-based quantum compile request.

    :param MetaData metadata: General information and optimization preferences.
    :param list[Node] nodes: List of all nodes forming the program graph.
    :param list[Edge] edges: Directed edges defining input-output relationships between nodes.
    """

    metadata: MetaData
    nodes: list[Annotated[Node, Field(discriminator="type")]]
    edges: list[Edge]


EnrichableNode = (
    BoundaryNode
    | GateNode
    | ParameterizedGateNode
    | LiteralNode
    | AncillaNode
    | OperatorNode
    | QubitNode
)


class SingleInsertMetaData(BaseModel):
    """
    Models the metadata of a single insert.
    """

    width: Annotated[int, Field(gt=0)] | None = None
    depth: Annotated[int, Field(gt=0)] | None = None


class SingleInsert(BaseModel):
    """
    Single insertion of an implementation for the enricher.
    """

    node: Annotated[EnrichableNode, Field(discriminator="type")]
    implementation: str
    metadata: SingleInsertMetaData


class InsertRequest(BaseModel):
    """
    Models a request for an implementation insert into the enricher.
    """

    inserts: list[SingleInsert]

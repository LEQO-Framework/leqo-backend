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

    :param optimizeWidth (int | None): If set, enables circuit width optimization with a user-defined priority.
    :param optimizeDepth (int | None): If set, enables circuit depth optimization with a user-defined priority.
    """

    optimizeWidth: int | None
    optimizeDepth: int | None


class MetaData(BaseModel, OptimizeSettings):
    """
    Contains metadata for a compile request, including versioning and optimization preferences.

    :param version (str): Version identifier of the project or model.
    :param name (str): Name of the quantum circuit or model.
    :param description (str): Human-readable description of the model.
    :param author (str): Author of the model.
    :param optimizeWidth (int | None): Optimization setting for reducing circuit width (optional).
    :param optimizeDepth (int | None): Optimization setting for reducing circuit depth (optional).
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

    :param id (str): Unique identifier for the node.
    :param label (str | None): Optional label for the node used for display purposes.
    """

    id: str
    label: str | None = None


class ImplementationNode(BaseNode):
    """
    Node containing a user-defined OpenQASM implementation.

    :param type (Literal["implementation"]): Constant value indicating this node type.
    :param implementation (str): Raw OpenQASM code associated with the node.
    """

    type: Literal["implementation"] = "implementation"
    implementation: str


# region Boundary Nodes
class EncodeValueNode(BaseNode):
    """
    Node representing quantum state encoding from classical values.

    :param type (Literal["encode"]): Constant value indicating this node type.
    :param encoding (Literal): Encoding scheme used (e.g. "amplitude", "basis", etc.).
    :param bounds (int): Indicates whether values are clamped (0 or 1).
    """

    type: Literal["encode"] = "encode"
    encoding: Literal["amplitude", "angle", "basis", "custom", "matrix", "schmidt"]
    bounds: int = Field(ge=0, default=0, le=1)


class PrepareStateNode(BaseNode):
    """
    Node for preparing known quantum states like Bell or GHZ.

    :param type (Literal["prepare"]): Constant value indicating this node type.
    :param quantumState (Literal): Type of quantum state to prepare (e.g. "ψ+", "ghz").
    :param size (int): Number of qubits involved in state preparation.
    """

    type: Literal["prepare"] = "prepare"
    quantumState: Literal["ϕ+", "ϕ-", "ψ+", "ψ-", "custom", "ghz", "uniform", "w"]
    size: int = Field(gt=0)


class SplitterNode(BaseNode):
    """
    Node that splits qubits into multiple branches.

    :param type (Literal["splitter"]): Constant value indicating this node type.
    :param numberOutputs (int): Number of output branches created.
    """

    type: Literal["splitter"] = "splitter"
    numberOutputs: int = Field(ge=2)


class MergerNode(BaseNode):
    """
    Node that merges multiple input branches into a single stream.

    :param type (Literal["merger"]): Constant value indicating this node type.
    :param numberInputs (int): Number of input branches merged.
    """

    type: Literal["merger"] = "merger"
    numberInputs: int = Field(ge=2)


class MeasurementNode(BaseNode):
    """
    Node performing quantum measurement on specified qubit indices.

    :param type (Literal["measure"]): Constant value indicating this node type.
    :param indices (list[int]): List of qubit indices to measure.
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

    :param type (Literal["qubit"]): Constant value indicating this node type.
    :param size (int): Number of qubits to allocate.
    """

    type: Literal["qubit"] = "qubit"
    size: int = Field(default=1, ge=1)


class GateNode(BaseNode):
    """
    Node representing application of a quantum gate.

    :param type (Literal["gate"]): Constant value indicating this node type.
    :param gate: The gate to apply (e.g., "x", "cnot", etc.).
    """

    type: Literal["gate"] = "gate"
    gate: OneQubitGate | TwoQubitGate | ThreeQubitGate | Literal["cnot", "toffoli"]


class ParameterizedGateNode(BaseNode):
    """
    Node representing a gate that requires a parameter (e.g., angle rotation).

    :param type (Literal["gate-with-param"]): Constant value indicating this node type.
    :param gate: The parameterized gate to apply.
    :param parameter (float): Value of the gate's parameter.
    """

    type: Literal["gate-with-param"] = "gate-with-param"
    gate: OneQubitGateWithAngle | TwoQubitGateWithParam | TwoQubitGateWithAngle
    parameter: float


# region Literals
class BitLiteralNode(BaseNode):
    """
    Node representing a fixed classical bit value (0 or 1).

    :param type (Literal["bit"]): Constant value indicating this node type.
    :param value (Literal[0, 1]): Bit value.
    """

    type: Literal["bit"] = "bit"
    value: Literal[0, 1]


class BoolLiteralNode(BaseNode):
    """
    Node representing a boolean literal.

    :param type (Literal["bool"]): Constant value indicating this node type.
    :param value (bool): Boolean value.
    """

    type: Literal["bool"] = "bool"
    value: bool


class IntLiteralNode(BaseNode):
    """
    Node representing an integer literal.

    :param type (Literal["int"]): Constant value indicating this node type.
    :param bitSize (int): Bit size of the integer.
    :param value (int): Integer value.
    """

    type: Literal["int"] = "int"
    bitSize: int = Field(default=32, ge=1)
    value: int


class FloatLiteralNode(BaseNode):
    """
    Node representing a floating-point literal.

    :param type (Literal["float"]): Constant value indicating this node type.
    :param bitSize (int): Bit size of the float.
    :param value (float): Float value.
    """

    type: Literal["float"] = "float"
    bitSize: int = Field(default=32, ge=1)
    value: float


LiteralNode = BitLiteralNode | BoolLiteralNode | IntLiteralNode | FloatLiteralNode
# endregion


class AncillaNode(BaseNode):
    """
    Node allocating ancillary qubits for temporary computation.

    :param type (Literal["ancilla"]): Constant value indicating this node type.
    :param size (int): Number of ancilla qubits allocated.
    """

    type: Literal["ancilla"] = "ancilla"
    size: int = Field(default=1, ge=1)


# region ControlFlow
class NestedBlock(BaseModel):
    """
    Represents a subgraph or code block used inside control flow nodes.

    :param nodes (list[NestableNode]): List of nodes within the block.
    :param edges (list[Edge]): Connections between the nodes.
    """

    nodes: list[NestableNode]
    edges: list[Edge]


class IfThenElseNode(BaseNode):
    """
    Node representing conditional execution.

    :param type (Literal["if-then-else"]): Constant value indicating this node type.
    :param condition (str): Condition expression used to branch execution.
    :param thenBlock (NestedBlock): Code block executed if the condition is true.
    :param elseBlock (NestedBlock): Code block executed if the condition is false.
    """

    type: Literal["if-then-else"] = "if-then-else"
    condition: str
    thenBlock: NestedBlock
    elseBlock: NestedBlock


class RepeatNode(BaseNode):
    """
    Node representing a repeat loop structure.

    :param type (Literal["repeat"]): Constant value indicating this node type.
    :param iterations (int): Number of loop iterations.
    :param block (NestedBlock): Code block to repeat.
    """

    type: Literal["repeat"] = "repeat"
    iterations: int = Field(gt=0)
    block: NestedBlock


ControlFlowNode = IfThenElseNode | RepeatNode
# endregion


class OperatorNode(BaseNode):
    """
    Node representing a classical operation (arithmetic, bitwise, comparison).

    :param type (Literal["operator"]): Constant value indicating this node type.
    :param operator (Literal): Type of operator (e.g., "+", "&", "==").
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

    :param source (tuple[str, int]): Tuple of (node_id, output_index).
    :param target (tuple[str, int]): Tuple of (node_id, input_index).
    :param size (int | None): Optional size override for the edge.
    :param identifier (str | None): Optional name or alias of the connection.
    """

    source: tuple[str, Annotated[int, Field(ge=0)]]
    target: tuple[str, Annotated[int, Field(ge=0)]]
    size: int | None = None
    identifier: str | None = None


class CompileRequest(BaseModel):
    """
    Top-level object representing a full graph-based quantum compile request.

    :param metadata (MetaData): General information and optimization preferences.
    :param nodes (list[Node]): List of all nodes forming the program graph.
    :param edges (list[Edge]): Directed edges defining input-output relationships between nodes.
    """

    metadata: MetaData
    nodes: list[Annotated[Node, Field(discriminator="type")]]
    edges: list[Edge]

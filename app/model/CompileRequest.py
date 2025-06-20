"""
This module defines the data models for compile requests.
It provides classes to model metadata, node data, and the complete compile request.
"""

from __future__ import annotations

from abc import ABC
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

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
    """

    optimizeWidth: int | None
    """If set, enables circuit width optimization with a user-defined priority."""

    optimizeDepth: int | None
    """If set, enables circuit depth optimization with a user-defined priority."""


class MetaData(BaseModel, OptimizeSettings):
    """
    Contains metadata for a compile request, including versioning and optimization preferences.
    """

    version: str
    """Version identifier of the project or model."""

    name: str
    """Name of the quantum circuit or model."""

    description: str
    """Human-readable description of the model."""

    author: str
    """Author of the model."""

    optimizeWidth: Annotated[int, Field(gt=0)] | None = None
    """Optimization setting for reducing circuit width (optional)."""

    optimizeDepth: Annotated[int, Field(gt=0)] | None = None
    """Optimization setting for reducing circuit depth (optional)."""

    model_config = ConfigDict(use_attribute_docstrings=True)


class BaseNode(BaseModel):
    """
    Abstract base class for all node types used in a compile request.
    """

    id: str
    """Unique identifier for the node."""

    label: str | None = None
    """Optional label for the node used for display purposes."""

    model_config = ConfigDict(use_attribute_docstrings=True)


class ImplementationNode(BaseNode):
    """
    Node containing a user-defined OpenQASM implementation.
    """

    type: Literal["implementation"] = "implementation"

    implementation: str
    """Raw OpenQASM code associated with the node."""

    model_config = ConfigDict(use_attribute_docstrings=True)


# region Boundary Nodes
class EncodeValueNode(BaseNode):
    """
    Node representing quantum state encoding from classical values.
    """

    type: Literal["encode"] = "encode"

    encoding: Literal["amplitude", "angle", "basis", "custom", "matrix", "schmidt"]
    """Encoding scheme used (e.g. "amplitude", "basis", etc.)."""

    bounds: int = Field(ge=0, default=0, le=1)
    """Indicates whether values are clamped (0 or 1)."""

    model_config = ConfigDict(use_attribute_docstrings=True)


class PrepareStateNode(BaseNode):
    """
    Node for preparing known quantum states like Bell or GHZ.
    """

    type: Literal["prepare"] = "prepare"

    quantumState: Literal["ϕ+", "ϕ-", "ψ+", "ψ-", "custom", "ghz", "uniform", "w"]
    """Type of quantum state to prepare (e.g. "ψ+", "ghz")."""

    size: int = Field(gt=0)
    """Number of qubits involved in state preparation."""

    model_config = ConfigDict(use_attribute_docstrings=True)


class SplitterNode(BaseNode):
    """
    Node that splits qubits into multiple branches.
    """

    type: Literal["splitter"] = "splitter"

    numberOutputs: int = Field(ge=2)
    """Number of output branches created."""

    model_config = ConfigDict(use_attribute_docstrings=True)


class MergerNode(BaseNode):
    """
    Node that merges multiple input branches into a single stream.
    """

    type: Literal["merger"] = "merger"

    numberInputs: int = Field(ge=2)
    """Number of input branches merged."""

    model_config = ConfigDict(use_attribute_docstrings=True)


class MeasurementNode(BaseNode):
    """
    Node performing quantum measurement on specified qubit indices.
    """

    type: Literal["measure"] = "measure"

    indices: list[Annotated[int, Field(ge=0)]]
    """List of qubit indices to measure."""

    model_config = ConfigDict(use_attribute_docstrings=True)


BoundaryNode = (
    EncodeValueNode | PrepareStateNode | SplitterNode | MergerNode | MeasurementNode
)
# endregion


class QubitNode(BaseNode):
    """
    Node representing qubit allocation.
    """

    type: Literal["qubit"] = "qubit"

    size: int = Field(default=1, ge=1)
    """Number of qubits to allocate."""

    model_config = ConfigDict(use_attribute_docstrings=True)


class GateNode(BaseNode):
    """
    Node representing application of a quantum gate.
    """

    type: Literal["gate"] = "gate"

    gate: OneQubitGate | TwoQubitGate | ThreeQubitGate | Literal["cnot", "toffoli"]
    """The gate to apply (e.g., "x", "cnot", etc.)."""

    model_config = ConfigDict(use_attribute_docstrings=True)


class ParameterizedGateNode(BaseNode):
    """
    Node representing a gate that requires a parameter (e.g., angle rotation).
    """

    type: Literal["gate-with-param"] = "gate-with-param"

    gate: OneQubitGateWithAngle | TwoQubitGateWithParam | TwoQubitGateWithAngle
    """The parameterized gate to apply."""

    parameter: float
    """Value of the gate's parameter."""

    model_config = ConfigDict(use_attribute_docstrings=True)


# region Literals
class BitLiteralNode(BaseNode):
    """
    Node representing a fixed classical bit value (0 or 1).
    """

    type: Literal["bit"] = "bit"

    value: Literal[0, 1]
    """Bit value."""

    model_config = ConfigDict(use_attribute_docstrings=True)


class BoolLiteralNode(BaseNode):
    """
    Node representing a boolean literal.
    """

    type: Literal["bool"] = "bool"

    value: bool
    """Boolean value."""

    model_config = ConfigDict(use_attribute_docstrings=True)


class IntLiteralNode(BaseNode):
    """
    Node representing an integer literal.
    """

    type: Literal["int"] = "int"

    bitSize: int = Field(default=32, ge=1)
    """"Bit size of the integer (optional)."""

    value: int
    """Integer value."""

    model_config = ConfigDict(use_attribute_docstrings=True)


class FloatLiteralNode(BaseNode):
    """
    Node representing a floating-point literal.
    """

    type: Literal["float"] = "float"

    bitSize: int = Field(default=32, ge=1)
    """Bit size of the float (optional)."""

    value: float
    """Float value."""

    model_config = ConfigDict(use_attribute_docstrings=True)


LiteralNode = BitLiteralNode | BoolLiteralNode | IntLiteralNode | FloatLiteralNode
# endregion


class AncillaNode(BaseNode):
    """
    Node allocating ancillary qubits for temporary computation.
    """

    type: Literal["ancilla"] = "ancilla"

    size: int = Field(default=1, ge=1)
    """Number of ancilla qubits allocated."""

    model_config = ConfigDict(use_attribute_docstrings=True)


# region ControlFlow
class NestedBlock(BaseModel):
    """
    Represents a subgraph or code block used inside control flow nodes.
    """

    nodes: list[NestableNode]
    """List of nodes within the block."""

    edges: list[Edge]
    """Connections between the nodes."""

    model_config = ConfigDict(use_attribute_docstrings=True)


class IfThenElseNode(BaseNode):
    """
    Node representing conditional execution.
    """

    type: Literal["if-then-else"] = "if-then-else"

    condition: str
    """Condition expression used to branch execution."""

    thenBlock: NestedBlock
    """Code block executed if the condition is true."""

    elseBlock: NestedBlock
    """Code block executed if the condition is false."""

    model_config = ConfigDict(use_attribute_docstrings=True)


class RepeatNode(BaseNode):
    """
    Node representing a repeat loop structure.
    """

    type: Literal["repeat"] = "repeat"

    iterations: int = Field(gt=0)
    """Number of loop iterations."""

    block: NestedBlock
    """Code block to repeat."""

    model_config = ConfigDict(use_attribute_docstrings=True)


ControlFlowNode = IfThenElseNode | RepeatNode
# endregion


class OperatorNode(BaseNode):
    """
    Node representing a classical operation (arithmetic, bitwise, comparison).
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
    """Type of operator (e.g., "+", "&", "==")."""

    model_config = ConfigDict(use_attribute_docstrings=True)


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
    """

    source: tuple[
        Annotated[str, Field(description="Source node Id")],
        Annotated[int, Field(ge=0, description="Output index of source node")],
    ]
    """Tuple of (node_id, output_index)."""

    target: tuple[
        Annotated[str, Field(description="Target node id")],
        Annotated[int, Field(ge=0, description="Input index of target node")],
    ]
    """Tuple of (node_id, input_index)."""

    size: int | None = None
    """Optional size override for the edge"""

    identifier: str | None = None
    """Optional name or alias of the connection."""

    model_config = ConfigDict(use_attribute_docstrings=True)


class CompileRequest(BaseModel):
    """
    Top-level object representing a full graph-based quantum compile request.
    """

    metadata: MetaData
    """General information and optimization preferences."""

    nodes: list[Annotated[Node, Field(discriminator="type")]]
    """List of all nodes forming the program graph."""

    edges: list[Edge]
    """Directed edges defining input-output relationships between nodes."""

    model_config = ConfigDict(use_attribute_docstrings=True)


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

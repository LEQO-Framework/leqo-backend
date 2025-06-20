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
    """

    version: str = Field(description="Version identifier of the project or model.")
    name: str = Field(description="Name of the quantum circuit or model.")
    description: str = Field(description="Human-readable description of the model.")
    author: str = Field(description="Author of the model.")
    optimizeWidth: Annotated[int, Field(gt=0)] | None = Field(
        default=None,
        description="Optimization setting for reducing circuit width (optional).",
    )
    optimizeDepth: Annotated[int, Field(gt=0)] | None = Field(
        default=None,
        description="Optimization setting for reducing circuit depth (optional).",
    )


class BaseNode(BaseModel):
    """
    Abstract base class for all node types used in a compile request.
    """

    id: str = Field(description="Unique identifier for the node.")
    label: str | None = Field(
        default=None,
        description="Optional label for the node used for display purposes.",
    )


class ImplementationNode(BaseNode):
    """
    Node containing a user-defined OpenQASM implementation.
    """

    type: Literal["implementation"] = "implementation"
    implementation: str = Field(
        description="Raw OpenQASM code associated with the node."
    )


# region Boundary Nodes
class EncodeValueNode(BaseNode):
    """
    Node representing quantum state encoding from classical values.
    """

    type: Literal["encode"] = "encode"
    encoding: Literal["amplitude", "angle", "basis", "custom", "matrix", "schmidt"] = (
        Field(description='Encoding scheme used (e.g. "amplitude", "basis", etc.).')
    )
    bounds: int = Field(
        ge=0,
        default=0,
        le=1,
        description="Indicates whether values are clamped (0 or 1).",
    )


class PrepareStateNode(BaseNode):
    """
    Node for preparing known quantum states like Bell or GHZ.
    """

    type: Literal["prepare"] = "prepare"
    quantumState: Literal["ϕ+", "ϕ-", "ψ+", "ψ-", "custom", "ghz", "uniform", "w"] = (
        Field(description='Type of quantum state to prepare (e.g. "ψ+", "ghz").')
    )
    size: int = Field(
        gt=0, description="Number of qubits involved in state preparation."
    )


class SplitterNode(BaseNode):
    """
    Node that splits qubits into multiple branches.
    """

    type: Literal["splitter"] = "splitter"
    numberOutputs: int = Field(ge=2, description="Number of output branches created.")


class MergerNode(BaseNode):
    """
    Node that merges multiple input branches into a single stream.
    """

    type: Literal["merger"] = "merger"
    numberInputs: int = Field(ge=2, description="Number of input branches merged.")


class MeasurementNode(BaseNode):
    """
    Node performing quantum measurement on specified qubit indices.
    """

    type: Literal["measure"] = "measure"
    indices: list[Annotated[int, Field(ge=0)]] = Field(
        description="List of qubit indices to measure."
    )


BoundaryNode = (
    EncodeValueNode | PrepareStateNode | SplitterNode | MergerNode | MeasurementNode
)
# endregion


class QubitNode(BaseNode):
    """
    Node representing qubit allocation.
    """

    type: Literal["qubit"] = "qubit"
    size: int = Field(default=1, ge=1, description="Number of qubits to allocate.")


class GateNode(BaseNode):
    """
    Node representing application of a quantum gate.
    """

    type: Literal["gate"] = "gate"
    gate: OneQubitGate | TwoQubitGate | ThreeQubitGate | Literal["cnot", "toffoli"] = (
        Field(description='The gate to apply (e.g., "x", "cnot", etc.).')
    )


class ParameterizedGateNode(BaseNode):
    """
    Node representing a gate that requires a parameter (e.g., angle rotation).
    """

    type: Literal["gate-with-param"] = "gate-with-param"
    gate: OneQubitGateWithAngle | TwoQubitGateWithParam | TwoQubitGateWithAngle = Field(
        description="The parameterized gate to apply."
    )
    parameter: float = Field(description="Value of the gate's parameter.")


# region Literals
class BitLiteralNode(BaseNode):
    """
    Node representing a fixed classical bit value (0 or 1).
    """

    type: Literal["bit"] = "bit"
    value: Literal[0, 1] = Field(description="Bit value.")


class BoolLiteralNode(BaseNode):
    """
    Node representing a boolean literal.
    """

    type: Literal["bool"] = "bool"
    value: bool = Field(description="Boolean value.")


class IntLiteralNode(BaseNode):
    """
    Node representing an integer literal.
    """

    type: Literal["int"] = "int"
    bitSize: int = Field(
        default=32, ge=1, description="Bit size of the integer (optional)."
    )
    value: int = Field(description="Integer value.")


class FloatLiteralNode(BaseNode):
    """
    Node representing a floating-point literal.
    """

    type: Literal["float"] = "float"
    bitSize: int = Field(
        default=32, ge=1, description="Bit size of the float (optional)."
    )
    value: float = Field(description="Float value.")


LiteralNode = BitLiteralNode | BoolLiteralNode | IntLiteralNode | FloatLiteralNode
# endregion


class AncillaNode(BaseNode):
    """
    Node allocating ancillary qubits for temporary computation.
    """

    type: Literal["ancilla"] = "ancilla"
    size: int = Field(
        default=1, ge=1, description="Number of ancilla qubits allocated."
    )


# region ControlFlow
class NestedBlock(BaseModel):
    """
    Represents a subgraph or code block used inside control flow nodes.
    """

    nodes: list[NestableNode] = Field(description="List of nodes within the block.")
    edges: list[Edge] = Field(description="Connections between the nodes.")


class IfThenElseNode(BaseNode):
    """
    Node representing conditional execution.
    """

    type: Literal["if-then-else"] = "if-then-else"
    condition: str = Field(description="Condition expression used to branch execution.")
    thenBlock: NestedBlock = Field(
        description="Code block executed if the condition is true."
    )
    elseBlock: NestedBlock = Field(
        description="Code block executed if the condition is false."
    )


class RepeatNode(BaseNode):
    """
    Node representing a repeat loop structure.
    """

    type: Literal["repeat"] = "repeat"
    iterations: int = Field(gt=0, description="Number of loop iterations.")
    block: NestedBlock = Field(description="Code block to repeat.")


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
    ] = Field(description='Type of operator (e.g., "+", "&", "==").')


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
    ] = Field(description="Tuple of (node_id, output_index).")
    target: tuple[
        Annotated[str, Field(description="Target node id")],
        Annotated[int, Field(ge=0, description="Input index of target node")],
    ] = Field(description="Tuple of (node_id, input_index).")
    size: int | None = Field(
        default=None, description="Optional size override for the edge."
    )
    identifier: str | None = Field(
        default=None, description="Optional name or alias of the connection."
    )


class CompileRequest(BaseModel):
    """
    Top-level object representing a full graph-based quantum compile request.
    """

    metadata: MetaData = Field(
        description="General information and optimization preferences."
    )
    nodes: list[Annotated[Node, Field(discriminator="type")]] = Field(
        description="List of all nodes forming the program graph."
    )
    edges: list[Edge] = Field(
        description="Directed edges defining input-output relationships between nodes."
    )


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

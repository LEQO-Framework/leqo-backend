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
    Optimization settings for a :class:`CompileRequest`.
    """

    optimizeWidth: int | None
    optimizeDepth: int | None


class MetaData(BaseModel, OptimizeSettings):
    """
    Models the metadata of a compile request.
    """

    version: str
    name: str
    description: str
    author: str
    optimizeWidth: Annotated[int, Field(gt=0)] | None = None
    optimizeDepth: Annotated[int, Field(gt=0)] | None = None


class BaseNode(BaseModel):
    """
    Models a node within a compile request.
    """

    id: str
    label: str | None = None


class ImplementationNode(BaseNode):
    """
    Special node that holds just an implementation.
    This is used in case the user manually enters an implementation in the frontend.
    """

    type: Literal["implementation"] = "implementation"
    implementation: str


# region Boundary Nodes
class EncodeValueNode(BaseNode):
    type: Literal["encode"] = "encode"
    encoding: Literal["amplitude", "angle", "basis", "custom", "matrix", "schmidt"]
    bounds: int = Field(ge=0, default=0, le=1)


class PrepareStateNode(BaseNode):
    type: Literal["prepare"] = "prepare"
    quantumState: Literal["ϕ+", "ϕ-", "ψ+", "ψ-", "custom", "ghz", "uniform", "w"]
    size: int = Field(gt=0)


class SplitterNode(BaseNode):
    type: Literal["splitter"] = "splitter"
    numberOutputs: int = Field(ge=2)


class MergerNode(BaseNode):
    type: Literal["merger"] = "merger"
    numberInputs: int = Field(ge=2)


class MeasurementNode(BaseNode):
    type: Literal["measure"] = "measure"
    indices: list[Annotated[int, Field(ge=0)]]


BoundaryNode = (
    EncodeValueNode | PrepareStateNode | SplitterNode | MergerNode | MeasurementNode
)
# endregion


class QubitNode(BaseNode):
    type: Literal["qubit"] = "qubit"
    size: int = Field(default=1, ge=1)


class GateNode(BaseNode):
    type: Literal["gate"] = "gate"
    gate: OneQubitGate | TwoQubitGate | ThreeQubitGate | Literal["cnot", "toffoli"]


class ParameterizedGateNode(BaseNode):
    type: Literal["gate-with-param"] = "gate-with-param"
    gate: OneQubitGateWithAngle | TwoQubitGateWithParam | TwoQubitGateWithAngle
    parameter: float


# region Literals
class BitLiteralNode(BaseNode):
    type: Literal["bit"] = "bit"
    value: Literal[0, 1]


class BoolLiteralNode(BaseNode):
    type: Literal["bool"] = "bool"
    value: bool


class IntLiteralNode(BaseNode):
    type: Literal["int"] = "int"
    bitSize: int = Field(default=32, ge=1)
    value: int


class FloatLiteralNode(BaseNode):
    type: Literal["float"] = "float"
    bitSize: int = Field(default=32, ge=1)
    value: float


LiteralNode = BitLiteralNode | BoolLiteralNode | IntLiteralNode | FloatLiteralNode
# endregion


class AncillaNode(BaseNode):
    type: Literal["ancilla"] = "ancilla"
    size: int = Field(default=1, ge=1)


# region ControlFlow
class NestedBlock(BaseModel):
    nodes: list[NestableNode]
    edges: list[Edge]


class IfThenElseNode(BaseNode):
    type: Literal["if-then-else"] = "if-then-else"
    condition: str
    thenBlock: NestedBlock
    elseBlock: NestedBlock


class RepeatNode(BaseNode):
    type: Literal["repeat"] = "repeat"
    iterations: int = Field(gt=0)
    block: NestedBlock


ControlFlowNode = IfThenElseNode | RepeatNode
# endregion


class OperatorNode(BaseNode):
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
    source: tuple[str, Annotated[int, Field(ge=0)]]
    target: tuple[str, Annotated[int, Field(ge=0)]]
    size: int | None = None
    identifier: str | None = None


class CompileRequest(BaseModel):
    """
    Models a complete compile request.
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
    meta: SingleInsertMetaData


class InsertRequest(BaseModel):
    """
    Models a request for an implementation insert into the enricher.
    """

    inserts: list[SingleInsert]

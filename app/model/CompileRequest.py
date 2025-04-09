"""
This module defines the data models for compile requests.
It provides classes to model metadata, node data, and the complete compile request.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class MetaData(BaseModel):
    """
    Models the metadata of a compile request.
    """

    version: str
    name: str
    description: str
    author: str
    optimizeWidth: Annotated[int, Field(ge=0)] | None = None
    optimizeDepth: Annotated[int, Field(ge=0)] | None = None


class _BaseNode(BaseModel):
    """
    Models a node within a compile request.
    """

    id: str
    label: str | None = None


class ImplementationNode(_BaseNode):
    type: Literal["implementation"] = "implementation"
    implementation: str


# region Boundary Nodes
class EncodeValueNode(_BaseNode):
    type: Literal["encode"] = "encode"
    encoding: Literal["amplitude", "angle", "basis", "custom", "matrix", "schmidt"]
    bounds: int = Field(ge=1)  # ToDo: ???


class PrepareStateNode(_BaseNode):
    type: Literal["prepare"] = "prepare"
    size: int = Field(ge=1)
    quantumState: Literal["ϕ+", "ϕ-", "ψ+", "ψ-", "custom", "ghz", "uniform", "w"]


class MeasurementNode(_BaseNode):
    type: Literal["measure"] = "measure"
    indices: list[Annotated[int, Field(ge=0)]]


BoundaryNode = EncodeValueNode | PrepareStateNode | MeasurementNode
# endregion


# region Circuit Nodes
class QubitNode(_BaseNode):
    type: Literal["qubit"] = "qubit"
    size: int = Field(default=1, ge=1)


class GateNode(_BaseNode):
    type: Literal["gate"] = "gate"
    gate: Literal["cnot", "toffoli", "h", "rx", "ry", "rz", "x", "y", "z"]


CircuitNode = QubitNode | GateNode
# endregion


# region Literals
# ToDo: Array support?


class BitLiteralNode(_BaseNode):
    type: Literal["bit"] = "bit"
    value: Literal[0, 1]


class BoolLiteralNode(_BaseNode):
    type: Literal["bool"] = "bool"
    value: bool


class IntLiteralNode(_BaseNode):
    type: Literal["int"] = "int"
    bitSize: int = Field(default=32, ge=1)
    value: int


class FloatLiteralNode(_BaseNode):
    type: Literal["float"] = "float"
    bitSize: int = Field(default=32, ge=1)
    value: float


LiteralNode = BitLiteralNode | BoolLiteralNode | IntLiteralNode | FloatLiteralNode
# endregion


# region ControlFlow
class IfThenElseNode(_BaseNode):
    type: Literal["if-then-else"] = "if-then-else"
    # ToDo: Condition?


class RepeatNode(_BaseNode):
    type: Literal["repeat"] = "repeat"
    # ToDo: ???


ControlFlowNode = IfThenElseNode | RepeatNode
# endregion


# region Operator
class OperatorNode(_BaseNode):
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
        "search",  # ToDo: ?
    ]


# endregion

Node = (
    ImplementationNode
    | BoundaryNode
    | CircuitNode
    | LiteralNode
    | ControlFlowNode
    | OperatorNode
)


class Edge(BaseModel):
    source: tuple[str, Annotated[int, Field(ge=0)]]
    target: tuple[str, Annotated[int, Field(ge=0)]]


class CompileRequest(BaseModel):
    """
    Models a complete compile request.
    """

    metadata: MetaData
    nodes: list[Annotated[Node, Field(discriminator="type")]]
    edges: list[Edge]

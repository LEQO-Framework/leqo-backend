from enum import Enum

from pydantic import BaseModel


class MetaData(BaseModel):
    version: str
    name: str
    description: str
    author: str
    id: str
    timestamp: str


class NodeIdRef(BaseModel):  # ToDo: remove after frontend changed inputs to type list[str]
    id: str


class NodeType(str, Enum):
    POSITION_NODE = "positionNode"
    STATE_PREPARATION_NODE = "statePreparationNode"
    GATE_NODE = "gateNode"
    OPERATION_NODE = "operationNode"
    ANCILLA_NODE = "ancillaNode"
    CLASSICAL_OUTPUT_OPERATION_NODE = "classicalOutputOperationNode"
    ARITHMETIC_OPERATOR_NODE = "arithmeticOperatorNode"
    MEASUREMENT_NODE = "measurementNode"


class NodeData(BaseModel):
    label: str
    inputs: list[NodeIdRef]  # ToDo: change to list[str]
    implementation: str
    implementationType: str
    uncomputeImplementationType: str
    uncomputeImplementation: str
    indices: str | None = None
    outputIdentifier: str


class Node(BaseModel):
    id: str
    type: NodeType
    data: NodeData


class CompileRequest(BaseModel):
    metadata: MetaData
    nodes: list[Node]

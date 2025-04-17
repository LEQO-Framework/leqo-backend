"""
This module defines the data models for compile requests.
It provides classes to model metadata, node data, and the complete compile request.
"""

from enum import StrEnum

from pydantic import BaseModel


class MetaData(BaseModel):
    """
    Models the metadata of a compile request.
    """

    version: str
    name: str
    description: str
    author: str
    timestamp: str


class NodeIdRef(
    BaseModel
):  # ToDo: remove after frontend changed inputs to type list[str]
    """
    Models a reference object containing the node ID.
    """

    id: str


class NodeType(StrEnum):
    """
    Enumeration of the various node types.
    """

    POSITION_NODE = "positionNode"
    STATE_PREPARATION_NODE = "statePreparationNode"
    GATE_NODE = "gateNode"
    OPERATION_NODE = "operationNode"
    ANCILLA_NODE = "ancillaNode"
    CLASSICAL_OUTPUT_OPERATION_NODE = "classicalOutputOperationNode"
    ARITHMETIC_OPERATOR_NODE = "arithmeticOperatorNode"
    MEASUREMENT_NODE = "measurementNode"


class NodeData(BaseModel):
    """
    Contains specific data for a node.
    """

    label: str
    inputs: list[NodeIdRef]  # ToDo: change to list[str]
    implementation: str
    implementationType: str
    uncomputeImplementationType: str
    uncomputeImplementation: str
    indices: str | None = None
    outputIdentifier: str


class Node(BaseModel):
    """
    Models a node within a compile request.
    """

    id: str
    type: NodeType
    data: NodeData


class CompileRequest(BaseModel):
    """
    Models a complete compile request.
    """

    metadata: MetaData
    nodes: list[Node]

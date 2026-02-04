"""
This module defines the data models for compile requests.
It provides classes to model metadata, node data, and the complete compile request.
"""

from __future__ import annotations

import re
from abc import ABC
from collections.abc import Iterable
from contextlib import suppress
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.openqasm3.stdgates import (
    OneQubitGate,
    OneQubitGateWithAngle,
    ThreeQubitGate,
    TwoQubitGate,
    TwoQubitGateWithAngle,
    TwoQubitGateWithParam,
)


def _infer_int_bit_size(value: int) -> int:
    """
    Derive the minimal two's-complement bit width required to represent value.
    """

    if value >= 0:
        return max(1, value.bit_length())
    return max(1, (-value - 1).bit_length() + 1)


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

    containsPlaceholder: bool | None = None
    """Specifies if the model contains placeholder."""

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

    @model_validator(mode="before")
    @classmethod
    def _normalize_state(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        normalized = data.copy()
        if normalized.get("type") == "statePreparationNode":
            normalized["type"] = "prepare"

        node_data = normalized.get("data")
        if isinstance(node_data, dict):
            if "quantumState" not in normalized:
                state_name = node_data.get("quantumStateName")
                if state_name is not None:
                    normalized["quantumState"] = str(state_name)
            if "size" not in normalized:
                size_value = node_data.get("size")
                if size_value is not None:
                    normalized["size"] = size_value

        if "quantumState" in normalized and normalized["quantumState"] is not None:
            normalized["quantumState"] = str(normalized["quantumState"]).lower()

        size_field = normalized.get("size")
        if isinstance(size_field, str):
            stripped = size_field.strip()
            if stripped:
                with suppress(ValueError):
                    normalized["size"] = int(stripped)

        return normalized


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

    @model_validator(mode="before")
    @classmethod
    def _normalize_measurement(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        normalized = data.copy()
        if normalized.get("type") == "measurementNode":
            normalized["type"] = "measure"

        node_data = normalized.get("data")
        node_dict = node_data if isinstance(node_data, dict) else None

        indices = cls._parse_indices(normalized.get("indices"))
        if indices is None and node_dict is not None:
            indices = cls._parse_indices(node_dict.get("indices"))
            if indices is None:
                indices = cls._infer_indices_from_inputs(node_dict.get("inputs"))

        if indices is not None:
            normalized["indices"] = indices

        return normalized

    @staticmethod
    def _coerce_indices(values: Iterable[Any]) -> list[int]:
        coerced: list[int] = []
        for raw in values:
            if isinstance(raw, int):
                coerced.append(raw)
                continue
            if isinstance(raw, str):
                stripped = raw.strip()
                if stripped:
                    with suppress(ValueError):
                        coerced.append(int(stripped))
        return coerced

    @classmethod
    def _parse_indices(cls, value: Any) -> list[int] | None:
        if isinstance(value, list):
            parsed = cls._coerce_indices(value)
            return parsed or None
        if isinstance(value, str):
            segments = [segment.strip() for segment in value.split(",")]
            parsed = cls._coerce_indices(segments)
            return parsed or None
        if isinstance(value, int):
            return [value]
        return None

    @staticmethod
    def _infer_indices_from_inputs(value: Any) -> list[int] | None:
        if not isinstance(value, list):
            return None
        logical_inputs = [
            entry
            for entry in value
            if not (isinstance(entry, dict) and "outputIdentifier" in entry)
        ]
        return list(range(len(logical_inputs))) if logical_inputs else None


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

    value: int | str
    """Integer value."""

    model_config = ConfigDict(use_attribute_docstrings=True)


class FloatLiteralNode(BaseNode):
    """
    Node representing a floating-point literal.
    """

    type: Literal["float"] = "float"

    bitSize: int = Field(default=32, ge=1)
    """Bit size of the float (optional)."""

    value: int | str
    """Float value."""

    model_config = ConfigDict(use_attribute_docstrings=True)


class ArrayLiteralNode(BaseNode):
    """
    Node representing an array of integers.
    """

    type: Literal["array"] = "array"

    values: list[int]
    """Ordered list of integer values in the array."""

    elementBitSize: int | None = Field(default=None, ge=1)
    """Bit width of each element in the array (optional)."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    @model_validator(mode="before")
    @classmethod
    def _coerce_values(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        normalized = data.copy()
        raw_values = normalized.get("values", normalized.get("value"))
        if isinstance(raw_values, str):
            parts = [
                part.strip()
                for part in raw_values.replace(";", ",").split(",")
                if part.strip() != ""
            ]
            normalized["values"] = [int(part) for part in parts]
        elif isinstance(raw_values, Iterable):
            normalized["values"] = [int(value) for value in raw_values]
        elif raw_values is not None:
            normalized["values"] = [int(raw_values)]
        else:
            normalized.setdefault("values", [])

        return normalized

    @model_validator(mode="after")
    def _default_bit_size(self) -> ArrayLiteralNode:
        if self.elementBitSize is None:
            bit_size = (
                max((_infer_int_bit_size(value) for value in self.values), default=1)
                if self.values
                else 1
            )
            self.elementBitSize = bit_size
        return self


LiteralNode = (
    BitLiteralNode
    | BoolLiteralNode
    | IntLiteralNode
    | FloatLiteralNode
    | ArrayLiteralNode
)
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

    @model_validator(mode="before")
    @classmethod
    def _normalize_edge(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        normalized = data.copy()

        def _convert_endpoint(field: str, handle_field: str) -> None:
            value = normalized.get(field)
            if isinstance(value, str):
                node_id = value
                index = 0
                handle = normalized.get(handle_field)
                if isinstance(handle, str):
                    if handle.endswith(node_id):
                        prefix = handle[: -len(node_id)]
                    else:
                        prefix = handle
                    match = re.search(r"(\d+)(?!.*\d)", prefix)
                    if match is not None:
                        index = int(match.group(1))
                normalized[field] = (node_id, index)

        _convert_endpoint("source", "sourceHandle")
        _convert_endpoint("target", "targetHandle")

        size_value = normalized.get("size")
        if isinstance(size_value, str):
            stripped = size_value.strip()
            if stripped:
                with suppress(ValueError):
                    normalized["size"] = int(stripped)

        return normalized


class CompileRequest(BaseModel):
    """
    Top-level object representing a full graph-based quantum compile request.
    """

    metadata: MetaData
    """General information and optimization preferences."""

    compilation_target: Literal["qasm", "workflow"] = "qasm"
    """Compilation target. Either "qasm" (default) or "workflow"."""

    nodes: list[Annotated[Node, Field(discriminator="type")]]
    """List of all nodes forming the program graph."""

    edges: list[Edge]
    """Directed edges defining input-output relationships between nodes."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    @model_validator(mode="before")
    @classmethod
    def _normalize_nodes(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        normalized = data.copy()
        nodes = normalized.get("nodes")
        if isinstance(nodes, list):
            converted_nodes: list[Any] = []
            for node in nodes:
                if isinstance(node, dict):
                    converted = node.copy()
                    node_type = converted.get("type")
                    if node_type == "statePreparationNode":
                        converted["type"] = "prepare"
                    elif node_type == "measurementNode":
                        converted["type"] = "measure"
                    elif node_type == "dataTypeNode":
                        data_field = converted.get("data")
                        if isinstance(data_field, dict):
                            data_type = data_field.get("dataType")
                            if (
                                isinstance(data_type, str)
                                and data_type.lower() == "array"
                            ):
                                converted["type"] = "array"
                                converted.setdefault("label", data_field.get("label"))
                                if "values" not in converted and "value" in data_field:
                                    converted["values"] = data_field["value"]
                                if (
                                    "elementBitSize" not in converted
                                    and "bitSize" in data_field
                                ):
                                    converted["elementBitSize"] = data_field["bitSize"]
                    converted_nodes.append(converted)
                else:
                    converted_nodes.append(node)
            normalized["nodes"] = converted_nodes

        return normalized


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

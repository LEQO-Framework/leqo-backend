"""
Basic program graph used withing the :mod:`app.processing`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID, uuid5

from networkx import DiGraph
from openqasm3.ast import Program

from app.model.data_types import (
    LeqoSupportedClassicalType,
)
from app.model.data_types import (
    QubitType as LeqoQubitType,
)

QubitIDs = list[int]

LeqoNamespace = UUID("1378f1f9-b705-404b-be6a-d1b3e29236d7")


@dataclass(frozen=True)
class ProgramNode:
    """Represents a node in a visual model of an openqasm3 program.

    :param name: The id given from the front-end.
    :param id: Unique ID of this node, used in the renaming.
    :param label: (Optional) Label given from the front-end.
    :param is_ancilla_node: This node is ancilla node in the model.
    """

    name: str
    label: str | None
    is_ancilla_node: bool
    id: UUID

    def __init__(
        self,
        name: str,
        label: str | None = None,
        is_ancilla_node: bool = False,
        id: UUID | None = None,
    ) -> None:
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "is_ancilla_node", is_ancilla_node)
        object.__setattr__(
            self,
            "id",
            id if id is not None else uuid5(LeqoNamespace, self.name),
        )


@dataclass(frozen=True)
class IOConnection:
    """Map output-reg from source to target input-reg with specified size."""

    source: tuple[ProgramNode, int]
    target: tuple[ProgramNode, int]


@dataclass()
class AncillaConnection:
    """Map output qubits from source to target input qubits.

    The qubits are identified via the id specified in :class:`app.processing.graph.IOInfo`.
    """

    source: tuple[ProgramNode, QubitIDs]
    target: tuple[ProgramNode, QubitIDs]


if TYPE_CHECKING:
    ProgramGraphBase = DiGraph[ProgramNode]
else:
    ProgramGraphBase = DiGraph


class ProgramGraph(ProgramGraphBase):
    """Internal representation of the program graph."""

    node_data: dict[ProgramNode, ProcessedProgramNode]
    edge_data: dict[
        tuple[ProgramNode, ProgramNode],
        list[IOConnection | AncillaConnection],
    ]

    def __init__(self) -> None:
        super().__init__()
        self.node_data = {}
        self.edge_data = {}

    def append_node(self, node: ProcessedProgramNode) -> None:
        super().add_node(node.raw)
        self.node_data[node.raw] = node

    def append_nodes(self, *nodes: ProcessedProgramNode) -> None:
        for node in nodes:
            self.append_node(node)

    def append_edge(self, edge: IOConnection | AncillaConnection) -> None:
        super().add_edge(edge.source[0], edge.target[0])
        self.edge_data.setdefault((edge.source[0], edge.target[0]), []).append(edge)

    def append_edges(self, *edges: IOConnection | AncillaConnection) -> None:
        for edge in edges:
            self.append_edge(edge)

    def get_data_node(self, node: ProgramNode) -> ProcessedProgramNode:
        return self.node_data[node]

    def get_data_edges(
        self,
        source: ProgramNode,
        target: ProgramNode,
    ) -> list[IOConnection | AncillaConnection]:
        return self.edge_data[(source, target)]


@dataclass()
class QubitInfo:
    """Store QubitIDs of declarations, reusable and dirty.

    :param declaration_to_ids: Maps declared names to corresponding qubits ids.
    :param required_reusable_ids: List of required reusable/fresh/uncomputed qubit ids.
    :param required_dirty_ids: List of required (possible) dirty qubits.
    :param returned_reusable_ids: List of returned reusable qubits.
    :param returned_uncomputable_ids: List of qubits that are reusable after uncompute.
    :param returned_dirty_ids: List of qubits that are always returned dirty.
    """

    declaration_to_ids: dict[str, QubitIDs] = field(default_factory=dict)
    required_reusable_ids: QubitIDs = field(default_factory=list)
    required_dirty_ids: QubitIDs = field(default_factory=list)
    returned_reusable_ids: QubitIDs = field(default_factory=list)
    returned_uncomputable_ids: QubitIDs = field(default_factory=list)
    returned_dirty_ids: QubitIDs = field(default_factory=list)


@dataclass()
class ClassicalIOInstance:
    """Single input/output from a snippet of type classical.

    :param name: Name of the annotated variable.
    :param type: Type of the annotated variable.
    """

    name: str
    type: LeqoSupportedClassicalType


@dataclass()
class QubitIOInstance:
    """Single input/output from a snippet of type qubits.

    :param name: Name of the annotated variable.
    :param ids: List of annotated qubit ids.
    """

    name: str
    ids: QubitIDs

    @property
    def type(self) -> LeqoQubitType:
        return LeqoQubitType(len(self.ids))


@dataclass()
class IOInfo:
    """Input/output info for a single snippet.

    :param inputs: Maps input-index to (Qubit/Classical)IOInstance.
    :param outputs: Maps output-index to (Qubit/Classical)IOInstance.
    """

    inputs: dict[int, QubitIOInstance | ClassicalIOInstance] = field(
        default_factory=dict,
    )
    outputs: dict[int, QubitIOInstance | ClassicalIOInstance] = field(
        default_factory=dict,
    )


@dataclass()
class ProcessedProgramNode:
    """Store a qasm snippet as string and AST.

    :param raw: The corresponding ProgramNode.
    :param implementation: The implementation as AST. Might be modified during processing.
    :param io: Input/output information required for connections.
    :param qubit: Qubit information required for optimization.
    """

    raw: ProgramNode
    implementation: Program
    io: IOInfo = field(default_factory=IOInfo)
    qubit: QubitInfo = field(default_factory=QubitInfo)

    @property
    def id(self) -> UUID:
        return self.raw.id

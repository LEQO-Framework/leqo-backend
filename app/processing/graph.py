"""
Basic program graph used withing the :mod:`app.processing`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from networkx import DiGraph
from openqasm3.ast import Program


@dataclass(frozen=True)
class ProgramNode:
    """Represents a node in a visual model of an openqasm3 program."""

    name: str
    implementation: str
    uncompute_implementation: str | None = None


@dataclass
class SectionInfo:
    """Store information scraped in preprocessing."""

    id: UUID
    io: IOInfo

    def __init__(self, uuid: UUID | None = None, io_info: IOInfo | None = None) -> None:
        self.id = uuid4() if uuid is None else uuid
        self.io = IOInfo() if io_info is None else io_info


@dataclass(frozen=True)
class ProcessedProgramNode:
    """Store a qasm snippet as string and AST."""

    raw: ProgramNode
    implementation: Program
    info: SectionInfo
    uncompute_implementation: Program | None


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

    source: tuple[ProgramNode, list[int]]
    target: tuple[ProgramNode, list[int]]


if TYPE_CHECKING:
    ProgramGraphBase = DiGraph[ProgramNode]
else:
    ProgramGraphBase = DiGraph


class ProgramGraph(ProgramGraphBase):
    """Internal representation of the program graph."""

    __node_data: dict[ProgramNode, ProcessedProgramNode]
    __edge_data: dict[
        tuple[ProgramNode, ProgramNode],
        list[IOConnection | AncillaConnection],
    ]

    def __init__(self) -> None:
        super().__init__()
        self.__node_data = {}
        self.__edge_data = {}

    def append_node(self, node: ProcessedProgramNode) -> None:
        super().add_node(node.raw)
        self.__node_data[node.raw] = node

    def append_nodes(self, *nodes: ProcessedProgramNode) -> None:
        for node in nodes:
            self.append_node(node)

    def append_edge(self, edge: IOConnection | AncillaConnection) -> None:
        super().add_edge(edge.source[0], edge.target[0])
        self.__edge_data.setdefault((edge.source[0], edge.target[0]), []).append(edge)

    def append_edges(self, *edges: IOConnection | AncillaConnection) -> None:
        for edge in edges:
            self.append_edge(edge)

    def get_data_node(self, node: ProgramNode) -> ProcessedProgramNode:
        return self.__node_data[node]

    def get_data_edges(
        self,
        source: ProgramNode,
        target: ProgramNode,
    ) -> list[IOConnection | AncillaConnection]:
        return self.__edge_data[(source, target)]


@dataclass()
class QubitInputInfo:
    """Store the input id and the corresponding register position."""

    input_index: int
    reg_position: int


@dataclass()
class QubitOutputInfo:
    """Store the output id and the corresponding register position."""

    output_index: int
    reg_position: int


@dataclass()
class QubitAnnotationInfo:
    """Store input, output and reusable info for a single qubit."""

    input: QubitInputInfo | None = None
    output: QubitOutputInfo | None = None
    reusable: bool = False
    dirty: bool = False


@dataclass()
class IOInfo:
    """Store input, output, dirty and reusable info for qubits in a qasm-snippet.

    For this purpose, every qubit (not qubit-reg) is given an id, based on declaration order.
    Then id_to_info maps these id's to the corresponding :class:`app.processing.graph.QubitAnnotationInfo`.
    Warning: uncompute parse not inplemented yet.

    :param declaration_to_ids: Maps declared qubit names to list of IDs.
    :param id_to_info: Maps IDs to their corresponding info objects.
    :param input_to_ids: Maps input indexes to their corresponding IDs.
    :param output_to_ids: Maps output indexes to their corresponding IDs.
    :param required_ancillas: Id list of required non-dirty ancillas.
    :param dirty_ancillas: Id list of required (possible) dirty ancillas.
    :param reusable_ancillas: Id list of reusable ancillas.
    :param reusable_after_uncompute: Id list of additional reusable ancillas after uncompute.
    :param returned_dirty_ancillas: Id list of ancillas that are returned dirty in any case.
    """

    declaration_to_ids: dict[str, list[int]] = field(default_factory=dict)
    id_to_info: dict[int, QubitAnnotationInfo] = field(default_factory=dict)
    input_to_ids: dict[int, list[int]] = field(default_factory=dict)
    output_to_ids: dict[int, list[int]] = field(default_factory=dict)
    required_ancillas: list[int] = field(default_factory=list)
    dirty_ancillas: list[int] = field(default_factory=list)
    reusable_ancillas: list[int] = field(default_factory=list)
    reusable_after_uncompute: list[int] = field(default_factory=list)
    returned_dirty_ancillas: list[int] = field(default_factory=list)

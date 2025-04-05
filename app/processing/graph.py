"""
Basic program graph used withing the :mod:`app.processing`.
"""

from __future__ import annotations

from dataclasses import dataclass
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


if TYPE_CHECKING:
    ProgramGraphBase = DiGraph[ProgramNode]
else:
    ProgramGraphBase = DiGraph


class ProgramGraph(ProgramGraphBase):
    """Internal representation of the program graph."""

    __node_data: dict[ProgramNode, ProcessedProgramNode]
    __edge_data: dict[tuple[ProgramNode, ProgramNode], IOConnection]

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

    def append_edge(self, edge: IOConnection) -> None:
        super().add_edge(edge.source[0], edge.target[0])
        self.__edge_data[(edge.source[0], edge.target[0])] = edge

    def append_edges(self, *edges: IOConnection) -> None:
        for edge in edges:
            self.append_edge(edge)

    def get_data_node(self, node: ProgramNode) -> ProcessedProgramNode:
        return self.__node_data[node]

    def get_data_edge(self, source: ProgramNode, target: ProgramNode) -> IOConnection:
        return self.__edge_data[(source, target)]


@dataclass()
class QubitInputInfo:
    """Store the input id and the corresponding register position."""

    id: int
    position: int


@dataclass()
class QubitOutputInfo:
    """Store the output id and the corresponding register position."""

    id: int
    position: int


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
    """

    declaration_to_id: dict[str, list[int]]
    alias_to_id: dict[str, list[int]]
    id_to_info: dict[int, QubitAnnotationInfo]
    input_to_ids: dict[int, list[int]]
    output_to_ids: dict[int, list[int]]

    def __init__(
        self,
        declaration_to_id: dict[str, list[int]] | None = None,
        alias_to_id: dict[str, list[int]] | None = None,
        id_to_info: dict[int, QubitAnnotationInfo] | None = None,
        input_to_ids: dict[int, list[int]] | None = None,
        output_to_ids: dict[int, list[int]] | None = None,
    ) -> None:
        """Construct IOInfo.

        :param declaration_to_id: Maps declared qubit names to list of IDs.
        :param alias_to_id: Maps alias qubit names to list of IDs.
        :param id_to_info: Maps IDs to their corresponding info objects.
        :param input_to_ids: Maps input indexes to their corresponding IDs.
        :param output_to_ids: Maps output indexes to their corresponding IDs.
        """
        self.declaration_to_id = declaration_to_id or {}
        self.alias_to_id = alias_to_id or {}
        self.id_to_info = id_to_info or {}
        self.input_to_ids = input_to_ids or {}
        self.output_to_ids = output_to_ids or {}

    def identifier_to_ids(self, identifier: str) -> list[int]:
        """Get list of IDs for identifier in alias or declaration."""
        try:
            return self.declaration_to_id[identifier]
        except KeyError:
            return self.alias_to_id[identifier]

    def identifier_to_infos(self, identifier: str) -> list[QubitAnnotationInfo]:
        """Get list of IO-info for identifier."""
        return [self.id_to_info[i] for i in self.identifier_to_ids(identifier)]

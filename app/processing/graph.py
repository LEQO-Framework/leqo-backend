from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

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
    """Stores information scraped in preprocessing"""

    id: UUID


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

    def __init__(self) -> None:
        super().__init__()
        self.__node_data = {}

    def append_node(self, node: ProcessedProgramNode) -> None:
        super().add_node(node.raw, data=ProcessedProgramNode)
        self.__node_data[node.raw] = node

    def append_nodes(self, *nodes: ProcessedProgramNode) -> None:
        for node in nodes:
            self.append_node(node)

    def append_edge(self, edge: IOConnection) -> None:
        super().add_edge(edge.source[0], edge.target[0], data=edge)

    def append_edges(self, *edges: IOConnection) -> None:
        for edge in edges:
            self.append_edge(edge)

    def get_node_data(self, node: ProgramNode) -> ProcessedProgramNode:
        return self.__node_data[node]

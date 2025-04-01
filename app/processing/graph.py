from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from networkx import DiGraph
from openqasm3.ast import Program

from app.openqasm3.parser import leqo_parse


@dataclass(frozen=True)
class QasmImplementation:
    """Store a qasm snippet as string and AST."""

    qasm: str
    ast: Program = field(hash=False)

    @staticmethod
    def create(value: str) -> QasmImplementation:
        return QasmImplementation(value, leqo_parse(value))


@dataclass(frozen=True)
class ProgramNode:
    """Represents a node in a visual model of an openqasm3 program."""

    id: str
    implementation: QasmImplementation
    uncompute_implementation: QasmImplementation | None = None


@dataclass(frozen=True)
class IOConnection:
    """Map output-reg from source to target input-reg with specified size."""

    source: tuple[ProgramNode, int]
    target: tuple[ProgramNode, int]


if TYPE_CHECKING:
    DiGraphWithProgramNode = DiGraph[ProgramNode]
else:
    DiGraphWithProgramNode = DiGraph


class ProgramGraph(DiGraphWithProgramNode):
    """Internal representation of the program graph."""

    def append_node(self, node: ProgramNode) -> None:
        return super().add_node(node)

    def append_edge(self, edge: IOConnection) -> None:
        return super().add_edge(edge.source[0], edge.target[0], data=edge)

    def append_nodes(self, nodes: Iterable[ProgramNode]) -> None:
        for node in nodes:
            self.append_node(node)

    def append_edges(self, edges: Iterable[IOConnection]) -> None:
        for edge in edges:
            self.append_edge(edge)


@dataclass
class SectionInfo:
    """Store the sorting order to a ProgramNode."""

    index: int
    node: ProgramNode

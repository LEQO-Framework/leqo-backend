from __future__ import annotations

from dataclasses import dataclass, field

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
    size: int


@dataclass
class SectionInfo:
    """Store the sorting order to a ProgramNode."""

    index: int
    node: ProgramNode

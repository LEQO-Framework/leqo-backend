from __future__ import annotations

from dataclasses import dataclass, field

from openqasm3.ast import Program

from app.openqasm3.parser import leqo_parse


@dataclass(frozen=True)
class QasmImplementation:
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


@dataclass
class SectionInfo:
    index: int
    node: ProgramNode
    io: SnippetIOInfo


@dataclass()
class SingleInputInfo:
    """Store the input id and the corresponding register position."""

    id: int
    position: int


@dataclass()
class SingleOutputInfo:
    """Store the output id and the corresponding register position."""

    id: int
    position: int


@dataclass()
class SingleIOInfo:
    """Store input, output and reusable info for a single qubit."""

    input: SingleInputInfo | None
    output: SingleOutputInfo | None
    reusable: bool

    def __init__(
        self,
        input: SingleInputInfo | None = None,
        output: SingleOutputInfo | None = None,
        reusable: bool | None = None,
    ) -> None:
        self.input = input
        self.output = output
        self.reusable = reusable or False


@dataclass()
class SnippetIOInfo:
    """Store input, output and reusable info for a qasm-snippet.

    :param declaration_to_id: Maps declared qubit names to list of IDs.
    :param alias_to_id: Maps alias qubit names to list of IDs.
    :param id_to_info: Maps IDs to their corresponding info objects.
    """

    declaration_to_id: dict[str, list[int]]
    alias_to_id: dict[str, list[int]]
    id_to_info: dict[int, SingleIOInfo]

    def __init__(
        self,
        declaration_to_id: dict[str, list[int]] | None = None,
        alias_to_id: dict[str, list[int]] | None = None,
        id_to_info: dict[int, SingleIOInfo] | None = None,
    ) -> None:
        self.declaration_to_id = declaration_to_id or {}
        self.alias_to_id = alias_to_id or {}
        self.id_to_info = id_to_info or {}

    def identifier_to_ids(self, identifier: str) -> list[int]:
        """Get list of IDs for identifier in alias or declaration."""
        try:
            return self.declaration_to_id[identifier]
        except KeyError:
            return self.alias_to_id[identifier]

    def identifier_to_infos(self, identifier: str) -> list[SingleIOInfo]:
        """Get list of IO-info for identifier."""
        return [self.id_to_info[i] for i in self.identifier_to_ids(identifier)]

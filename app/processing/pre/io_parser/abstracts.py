from __future__ import annotations

from abc import ABC, abstractmethod
from io import UnsupportedOperation
from typing import Any, Generic, TypeVar

from openqasm3.ast import (
    AliasStatement,
    ClassicalDeclaration,
    Concatenation,
    Expression,
    Identifier,
    IndexExpression,
    QubitDeclaration,
)

from app.processing.io_info import (
    RegIOInfo,
)
from app.processing.utils import expr_to_int, parse_qasm_index

T = TypeVar("T")
RT = TypeVar("RT", bound=RegIOInfo[Any])


class IOInfoBuilder(Generic[T], ABC):
    """Abstract class for io info constructors for various types."""

    @abstractmethod
    def handle_declaration(
        self,
        declaration: QubitDeclaration | ClassicalDeclaration,
        input_id: int | None,
        dirty: bool = False,
    ) -> None:
        pass

    @abstractmethod
    def handle_alias(
        self,
        alias: AliasStatement,
        output_id: int | None,
        reusable: bool,
    ) -> None:
        pass

    @abstractmethod
    def finish(self) -> None:
        pass


class RegIOInfoBuilder(Generic[RT], IOInfoBuilder[RT], ABC):
    next_id: int
    io: RT
    alias_to_ids: dict[str, list[int]]

    def __init__(self, io: RT) -> None:
        self.next_id = 0
        self.io = io
        self.alias_to_ids = {}

    def identifier_to_ids(self, identifier: str) -> list[int] | None:
        """Get ids via declaration_to_ids or alias_to_ids."""
        result = self.io.declaration_to_ids.get(identifier)
        return self.alias_to_ids.get(identifier) if result is None else result

    def declaration_size_to_ids(self, size: Expression | None) -> list[int]:
        reg_size = expr_to_int(size) if size is not None else 1
        result = []
        for _ in range(reg_size):
            result.append(self.next_id)
            self.next_id += 1
        return result

    def alias_expr_to_ids(
        self,
        value: Identifier | IndexExpression | Concatenation | Expression,
    ) -> list[int] | None:
        """Recursively get IDs list for alias expression."""
        match value:
            case IndexExpression():
                collection = value.collection
                if not isinstance(collection, Identifier):
                    msg = f"Unsupported expression in alias: {type(collection)}"
                    raise TypeError(msg)
                source = self.identifier_to_ids(collection.name)
                if source is None:
                    return None
                indices = parse_qasm_index([value.index], len(source))
                return [source[i] for i in indices]
            case Identifier():
                return self.identifier_to_ids(value.name)
            case Concatenation():
                lhs = self.alias_expr_to_ids(value.lhs)
                rhs = self.alias_expr_to_ids(value.rhs)
                if lhs is None or rhs is None:
                    return None
                return lhs + rhs
            case Expression():
                msg = f"Unsupported expression in alias: {type(value)}"
                raise UnsupportedOperation(msg)
            case _:
                msg = f"{type(value)} is not implemented as alias expression"
                raise NotImplementedError(msg)

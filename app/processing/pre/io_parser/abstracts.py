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
    SizedIOInfo,
)
from app.processing.utils import expr_to_int, parse_qasm_index

T = TypeVar("T")
RT = TypeVar("RT", bound=RegIOInfo[Any])
ST = TypeVar("ST", bound=SizedIOInfo)


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
    __next_id: int
    __stored_alias_ids: dict[str, list[int]]
    io: RT

    def __init__(self, io: RT) -> None:
        self.__next_id = 0
        self.__stored_alias_ids = {}
        self.io = io

    def __identifier_to_ids(self, identifier: str) -> list[int]:
        """Get ids via declaration_to_ids or alias_to_ids."""
        result = self.io.declaration_to_ids.get(identifier)
        return self.__stored_alias_ids[identifier] if result is None else result

    def __rec_alias_expr_to_ids(
        self,
        value: Identifier | IndexExpression | Concatenation | Expression,
    ) -> list[int]:
        """Recursively get IDs list for alias expression."""
        match value:
            case IndexExpression():
                collection = value.collection
                if not isinstance(collection, Identifier):
                    msg = f"Unsupported expression in alias: {type(collection)}"
                    raise TypeError(msg)
                source = self.__identifier_to_ids(collection.name)
                indices = parse_qasm_index([value.index], len(source))
                return [source[i] for i in indices]
            case Identifier():
                return self.__identifier_to_ids(value.name)
            case Concatenation():
                lhs = self.__rec_alias_expr_to_ids(value.lhs)
                rhs = self.__rec_alias_expr_to_ids(value.rhs)
                return lhs + rhs
            case Expression():
                msg = f"Unsupported expression in alias: {type(value)}"
                raise UnsupportedOperation(msg)
            case _:
                msg = f"{type(value)} is not implemented as alias expression"
                raise NotImplementedError(msg)

    def declaration_size_to_ids(self, size: Expression | None) -> list[int]:
        reg_size = expr_to_int(size) if size is not None else 1
        result = []
        for _ in range(reg_size):
            result.append(self.__next_id)
            self.__next_id += 1
        return result

    def alias_to_ids(
        self,
        alias: AliasStatement,
    ) -> list[int]:
        result = self.__rec_alias_expr_to_ids(alias.value)
        if len(result) == 0:
            msg = f"Unable to resolve IDs of alias {alias}"
            raise RuntimeError(msg)
        self.__stored_alias_ids[alias.target.name] = result
        return result


class SizedIOInfoBuilder(Generic[ST], IOInfoBuilder[ST], ABC):
    __next_id: int
    __stored_alias_id: dict[str, int]
    io: ST

    def __init__(self, io: ST) -> None:
        self.__next_id = 0
        self.__stored_alias_id = {}
        self.io = io

    def __identifier_to_id(self, identifier: str) -> int:
        """Get ids via declaration_to_ids or alias_to_ids."""
        result = self.io.declaration_to_id.get(identifier)
        return self.__stored_alias_id[identifier] if result is None else result

    def declaration_next_id(self) -> int:
        result = self.__next_id
        self.__next_id += 1
        return result

    def __alias_expr_to_id(
        self,
        value: Identifier | IndexExpression | Concatenation | Expression,
    ) -> int:
        match value:
            case IndexExpression():
                msg = f"Unsupported: indexed alias in sized type: {value}."
                raise UnsupportedOperation(msg)
            case Identifier():
                return self.__identifier_to_id(value.name)
            case Concatenation():
                msg = f"Unsupported: concatenated alias in sized type: {value}."
                raise UnsupportedOperation(msg)
            case Expression():
                msg = f"Unsupported expression in alias: {type(value)}"
                raise UnsupportedOperation(msg)
            case _:
                msg = f"{type(value)} is not implemented as alias expression"
                raise NotImplementedError(msg)

    def alias_to_id(
        self,
        alias: AliasStatement,
    ) -> int:
        result = self.__alias_expr_to_id(alias.value)
        self.__stored_alias_id[alias.target.name] = result
        return result

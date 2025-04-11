"""Abstract builder classes with lots of helper methods."""

from __future__ import annotations

from abc import ABC, abstractmethod
from io import UnsupportedOperation
from typing import Any, Generic, TypeVar

from openqasm3.ast import (
    AliasStatement,
    BoolType,
    ClassicalDeclaration,
    Concatenation,
    Expression,
    FloatType,
    Identifier,
    IndexExpression,
    IntType,
    QubitDeclaration,
)

from app.processing.io_info import (
    BOOL_SIZE,
    DEFAULT_FLOAT_SIZE,
    DEFAULT_INT_SIZE,
    RegIOInfo,
    SizedIOInfo,
)
from app.processing.utils import expr_to_int, parse_qasm_index

T = TypeVar("T")
RT = TypeVar("RT", bound=RegIOInfo[Any])
ST = TypeVar("ST", bound=SizedIOInfo)


class IOInfoBuilder(Generic[T], ABC):
    """Abstract class for all IOInfo builders.

    No helper methods here, this is the interface used by all builders.
    """

    @abstractmethod
    def handle_declaration(
        self,
        declaration: QubitDeclaration | ClassicalDeclaration,
        input_id: int | None,
        dirty: bool = False,
    ) -> None:
        """Will be called by visitor on declarations if type was detected."""

    @abstractmethod
    def handle_alias(
        self,
        alias: AliasStatement,
        output_id: int | None,
        reusable: bool,
    ) -> None:
        """Will be called by visitor on aliases if type was detected."""

    @abstractmethod
    def finish(self) -> None:
        """Will be called by visitor at the very end.

        Currently only used by the qubit builder.
        """


class RegIOInfoBuilder(Generic[RT], IOInfoBuilder[RT], ABC):
    """Abstract builder for register-based types.

    Has helper methods to get ids for a given declaration/alias.
    Stores all previous ids to dissolve aliases.
    """

    __next_id: int
    __stored_alias_ids: dict[str, list[int]]
    io: RT

    def __init__(self, io: RT) -> None:
        """Construct RegIOInfoBuilder.

        :param io: The io (based on RegIOInfo) to be modified in-place.
        """
        self.__next_id = 0
        self.__stored_alias_ids = {}
        self.io = io

    def __identifier_to_ids(self, identifier: str) -> list[int]:
        """Get ids via declaration or alias storage."""
        result = self.io.declaration_to_ids.get(identifier)
        return self.__stored_alias_ids[identifier] if result is None else result

    def __rec_alias_expr_to_ids(
        self,
        value: Identifier | IndexExpression | Concatenation | Expression,
    ) -> list[int]:
        """Recursively get ids for alias expression."""
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
        """Create and return new ids for given declaration size."""
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
        """Get ids for given alias statement.

        Use the recursive __rec_alias_expr_to_ids and update the alias storage.
        """
        result = self.__rec_alias_expr_to_ids(alias.value)
        if len(result) == 0:
            msg = f"Unable to resolve IDs of alias {alias}"
            raise RuntimeError(msg)
        self.__stored_alias_ids[alias.target.name] = result
        return result


class SizedIOInfoBuilder(Generic[ST], IOInfoBuilder[ST], ABC):
    """Abstract builder for sized types.

    Has helper methods to get id for a given declaration/alias.
    Stores all previous ids to dissolve aliases.
    """

    __next_id: int
    __stored_alias_id: dict[str, int]
    io: ST

    def __init__(self, io: ST) -> None:
        """Construct SizedIOInfoBuilder.

        :param io: The io (based on SizedIOInfo) to be modified in-place.
        """
        self.__next_id = 0
        self.__stored_alias_id = {}
        self.io = io

    def __identifier_to_id(self, identifier: str) -> int:
        """Get id via declaration or alias storage."""
        result = self.io.declaration_to_id.get(identifier)
        return self.__stored_alias_id[identifier] if result is None else result

    def __alias_expr_to_id(
        self,
        value: Identifier | IndexExpression | Concatenation | Expression,
    ) -> int:
        """Get id from alias expresssion.

        Resolves for single identifier and returns stored id for him.
        Raises error on non-identifier value.
        """
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

    def declaration_next_id(self) -> int:
        """Get next id for declaration."""
        result = self.__next_id
        self.__next_id += 1
        return result

    def declaration_to_size(self, declaration: ClassicalDeclaration) -> int:
        """Get size of given declaration.

        Extract size from AST or use default based on type.
        """
        typ = declaration.type
        match typ:
            case IntType():
                return (
                    expr_to_int(typ.size) if typ.size is not None else DEFAULT_INT_SIZE
                )
            case FloatType():
                return (
                    expr_to_int(typ.size)
                    if typ.size is not None
                    else DEFAULT_FLOAT_SIZE
                )
            case BoolType():
                return BOOL_SIZE
            case _:
                msg = f"'declaration_to_size' unsupported type: {type(typ)}"
                raise RuntimeError(msg)

    def alias_to_id(
        self,
        alias: AliasStatement,
    ) -> int:
        """Get id for given alias statement.

        Use the __alias_expr_to_id and update the alias storage.
        """
        result = self.__alias_expr_to_id(alias.value)
        self.__stored_alias_id[alias.target.name] = result
        return result

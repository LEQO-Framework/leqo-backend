"""
OpenQasm data-types that are supported by the leqo-backend.
"""

from dataclasses import dataclass

from openqasm3.ast import BitType as AstBitType
from openqasm3.ast import BoolType as AstBoolType
from openqasm3.ast import FloatType as AstFloatType
from openqasm3.ast import IntegerLiteral
from openqasm3.ast import IntType as AstIntType

DEFAULT_INT_SIZE = 32
DEFAULT_FLOAT_SIZE = 32
BOOL_SIZE = 1


@dataclass(frozen=True)
class QubitType:
    """
    A single qubit or qubit register.
    """

    size: int | None


@dataclass(frozen=True)
class ClassicalType:
    """
    Base class for classical data types.
    """


@dataclass(frozen=True)
class BitType(ClassicalType):
    """
    A single bit or bit-array.
    """

    size: int | None

    @staticmethod
    def with_size(size: int | None) -> "BitType":
        return BitType(size)

    def to_ast(self) -> AstBitType:
        return AstBitType(None if self.size is None else IntegerLiteral(self.size))


@dataclass(frozen=True)
class BoolType(ClassicalType):
    """
    A single boolean.
    """

    @property
    def size(self) -> int:
        return BOOL_SIZE

    @staticmethod
    def with_size(size: int | None) -> "BoolType":
        if size is not None and size != BOOL_SIZE:
            raise ValueError(f"size must be {BOOL_SIZE}")

        return BoolType()

    def to_ast(self) -> AstBoolType:
        return AstBoolType()


@dataclass(frozen=True)
class IntType(ClassicalType):
    """
    An integer with size in bits.
    """

    size: int

    @staticmethod
    def with_size(size: int | None) -> "IntType":
        return IntType(DEFAULT_INT_SIZE if size is None else size)

    def to_ast(self) -> AstIntType:
        return AstIntType(IntegerLiteral(self.size))


@dataclass(frozen=True)
class FloatType(ClassicalType):
    """
    A float with size in bits.
    """

    size: int

    @staticmethod
    def with_size(size: int | None) -> "FloatType":
        return FloatType(DEFAULT_FLOAT_SIZE if size is None else size)

    def to_ast(self) -> AstFloatType:
        return AstFloatType(IntegerLiteral(self.size))


@dataclass(frozen=True)
class FileType(ClassicalType):
    """
    A file reference (URL or file path).
    This type represents external data sources for ML plugins.
    """

    @property
    def size(self) -> int:
        """Files don't have a fixed bit size, return 0."""
        return 0

    @staticmethod
    def with_size(size: int | None) -> "FileType":
        """Size parameter is ignored for file types."""
        return FileType()


LeqoSupportedClassicalType = IntType | FloatType | BitType | BoolType | FileType
LeqoSupportedType = QubitType | LeqoSupportedClassicalType

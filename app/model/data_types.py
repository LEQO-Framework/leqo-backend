"""OpenQasm data-types that are supported by the leqo-backend."""

from dataclasses import dataclass

DEFAULT_INT_SIZE = 32
DEFAULT_FLOAT_SIZE = 32
BOOL_BIT_SIZE = 1


@dataclass(frozen=True)
class QubitType:
    """A single qubit or qubit register."""

    size: int | None


@dataclass(frozen=True)
class ClassicalType:
    """Base class for classical data types."""


@dataclass(frozen=True)
class BitType(ClassicalType):
    """A single bit or bit-array."""

    size: int | None

    @staticmethod
    def with_size(size: int | None) -> "BitType":
        return BitType(size)


@dataclass(frozen=True)
class BoolType(ClassicalType):
    """A single boolean."""

    @property
    def size(self) -> int:
        return BOOL_BIT_SIZE

    @staticmethod
    def with_size(size: int | None) -> "BoolType":
        if size is not None and size != BOOL_BIT_SIZE:
            raise ValueError(f"size must be {BOOL_BIT_SIZE}")

        return BoolType()


@dataclass(frozen=True)
class IntType(ClassicalType):
    """An integer with size in bits."""

    size: int

    @staticmethod
    def with_size(size: int | None) -> "IntType":
        return IntType(DEFAULT_INT_SIZE if size is None else size)


@dataclass(frozen=True)
class FloatType(ClassicalType):
    """A float with size in bits."""

    size: int

    @staticmethod
    def with_size(size: int | None) -> "FloatType":
        return FloatType(DEFAULT_FLOAT_SIZE if size is None else size)


LeqoSupportedClassicalType = IntType | FloatType | BitType | BoolType
LeqoSupportedType = QubitType | LeqoSupportedClassicalType

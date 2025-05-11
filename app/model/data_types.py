"""
OpenQasm data-types that are supported by the leqo-backend.
"""

from dataclasses import dataclass

DEFAULT_BIT_SIZE = 1
DEFAULT_INT_SIZE = 32
DEFAULT_FLOAT_SIZE = 32
BOOL_BIT_SIZE = 1


@dataclass(frozen=True)
class QubitType:
    """
    A single qubit or qubit register.
    """

    reg_size: int

    @property
    def bit_size(self) -> int:
        return self.reg_size


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

    bit_size: int

    @staticmethod
    def with_bit_size(bit_size: int) -> "BitType":
        return BitType(bit_size)


@dataclass(frozen=True)
class BoolType(ClassicalType):
    """
    A single boolean or boolean register.
    """

    @property
    def bit_size(self) -> int:
        return BOOL_BIT_SIZE

    @staticmethod
    def with_bit_size(bit_size: int) -> "BoolType":
        if bit_size != BOOL_BIT_SIZE:
            raise ValueError(f"bit_size must be {BOOL_BIT_SIZE}")

        return BoolType()


@dataclass(frozen=True)
class IntType(ClassicalType):
    """
    An integer with size in bits.
    """

    bit_size: int

    @staticmethod
    def with_bit_size(bit_size: int) -> "IntType":
        return IntType(bit_size)


@dataclass(frozen=True)
class FloatType(ClassicalType):
    """
    A float with size in bits.
    """

    bit_size: int

    @staticmethod
    def with_bit_size(bit_size: int) -> "FloatType":
        return FloatType(bit_size)


LeqoSupportedClassicalType = IntType | FloatType | BitType | BoolType
LeqoSupportedType = QubitType | LeqoSupportedClassicalType

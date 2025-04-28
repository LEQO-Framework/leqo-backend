"""
OpenQasm data-types that are supported by the leqo-backend.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class QubitType:
    """
    A single qubit or qubit register.
    """

    reg_size: int


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

    reg_size: int


@dataclass(frozen=True)
class BoolType(ClassicalType):
    """
    A single boolean or boolean register.
    """


@dataclass(frozen=True)
class IntType(ClassicalType):
    """
    An integer with size in bits.
    """

    bit_size: int


@dataclass(frozen=True)
class FloatType(ClassicalType):
    """
    A float with size in bits.
    """

    bit_size: int


LeqoSupportedClassicalType = IntType | FloatType | BitType | BoolType
LeqoSupportedType = QubitType | LeqoSupportedClassicalType

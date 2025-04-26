"""
ToDO
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class QubitType:
    reg_size: int


@dataclass(frozen=True)
class BitType:
    reg_size: int


@dataclass(frozen=True)
class BoolType:
    pass


@dataclass(frozen=True)
class IntType:
    bitSize: int


@dataclass(frozen=True)
class FloatType:
    bitSize: int


LeqoSupportedType = QubitType | IntType | FloatType | BitType | BoolType

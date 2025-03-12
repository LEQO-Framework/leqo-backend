from dataclasses import dataclass
from enum import Enum


class QasmDataType(Enum):
    QUBIT = "qubit"


@dataclass
class SectionGlobal:
    type: QasmDataType
    isInput: bool
    isOutput: bool
    isReset: bool


@dataclass
class SectionInfo:
    index: int
    globals: dict[str, SectionGlobal]

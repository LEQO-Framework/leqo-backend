from dataclasses import dataclass
from enum import Enum


class QasmDataType(Enum):
    QUBIT = "qubit"


@dataclass
class SectionGlobal:
    type: QasmDataType
    inputIndex: int | None
    outputIndex: int | None


@dataclass
class SectionInfo:
    index: int
    globals: dict[str, SectionGlobal]

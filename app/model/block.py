from enum import Enum
from typing import List, Dict

from pydantic import BaseModel


class BlockType(str, Enum):
    QUANTUM_GATE = "quantum-gate"
    MEASUREMENT = "measurement"
    CLASSICAL_OPERATION = "classical-operation"


class Block(BaseModel):
    id: str
    type: BlockType
    label: str
    description: str | None = None
    qasm: str
    connections: List[str] | None = None
    dependencies: List[str] | None = None
    parameters: Dict[str, str] | None = None

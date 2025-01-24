from enum import Enum

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
    connections: list[str] | None = None
    dependencies: list[str] | None = None
    parameters: dict[str, str] | None = None

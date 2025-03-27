from dataclasses import dataclass

from openqasm3.ast import Program


@dataclass(frozen=True)
class ModelNode:
    """
    Represents a node in a visual model of an openqasm3 program.
    """

    id: str
    Implementation: Program
    UncomputeImplementation: Program | None = None

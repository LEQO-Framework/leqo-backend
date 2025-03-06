"""Ensure unique imports at the front of the program."""

from openqasm3.ast import Include, Program
from openqasm3.visitor import QASMTransformer


class SortImports(QASMTransformer[None]):
    """Unique imports at the front.

    Makes following changes:
    - remove duplicate imports
    - move imports at the top
    """

    seen: dict[str, Include]

    def __init__(self) -> None:
        """Initialize data structures."""
        self.seen = {}

    def visit_Include(self, node: Include) -> None:
        """Store and remove all includes.

        :param node: The statement to process
        :return: None removes the node
        """
        self.seen[node.filename] = node

    def visit_Program(self, node: Program) -> Program:
        """Execute a normal (generic) visit, then add removed imports back."""
        program = self.generic_visit(node)
        if not isinstance(program, Program):
            msg = f"SortImports: generic_visit returned non-Program: {program}"
            raise TypeError(msg)
        program.statements = list(self.seen.values()) + program.statements
        return program

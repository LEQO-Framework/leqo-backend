"""Ensure unique imports at the front of the program."""

from openqasm3.ast import Include, Program
from openqasm3.visitor import QASMTransformer

from app.processing.utils import cast_to_program


class SortImportsTransformer(QASMTransformer[None]):
    """
    Create unique imports at the top.

    Makes following changes:

    - remove duplicate imports
    - move imports at the top
    """

    seen: dict[str, Include]

    def __init__(self) -> None:
        self.seen = {}

    def visit_Include(self, node: Include) -> None:
        """
        Store and remove all includes.

        :param node: The statement to process
        :return: None removes the node
        """
        self.seen[node.filename] = node

    def visit_Program(self, node: Program) -> Program:
        """
        Execute a normal (generic) visit, then add removed imports back.
        """
        program = cast_to_program(self.generic_visit(node))
        program.statements = list(self.seen.values()) + program.statements
        return program

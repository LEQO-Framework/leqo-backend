from typing import Any, override

from openqasm3.ast import Include, Program, QASMNode
from openqasm3.visitor import QASMTransformer


class SortImports(QASMTransformer[None]):
    """
    Makes following changes to the imports:
    - remove dublicates
    - list them all at the top of the program
    """

    seen: dict[str, Include]

    def __init__(self) -> None:
        self.seen = {}

    def visit_Include(self, node: Include) -> None:
        """
        Store and remove all includes, there are added later.

        :param node: The statement to process
        :return: None removes the node
        """

        self.seen[node.filename] = node

    def transform(self, program: Program) -> Program:
        """
        Transforms the program to have unique imports at the top.
        """
        program = self.visit(program)
        program.statements = list(self.seen.values()) + program.statements
        return program

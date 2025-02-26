from typing import Any, override

from openqasm3.ast import Include, Program, QASMNode
from openqasm3.visitor import QASMTransformer


class Imports(QASMTransformer[None]):
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

    @override
    def visit(self, node: QASMNode, context: object | None = None) -> Any | None:
        """
        Execute normal visit to remove imports, than add them to the beginning.
        """
        breakpoint()
        program: Program = super().visit(node, None)
        program.statements = list(self.seen.values()) + program.statements
        return program

from openqasm3.ast import Include, Program
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

    def visit_Program(self, node: Program) -> Program:
        """
        Executes a normal (generic) visit first, then add removed imports back.
        """
        program = self.generic_visit(node)
        if not isinstance(program, Program):
            raise RuntimeError("This can't happen.")
        program.statements = list(self.seen.values()) + program.statements
        return program

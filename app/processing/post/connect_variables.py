"""Connect variables via renaming based on provided specification."""

from openqasm3.ast import Identifier, QASMNode, QubitDeclaration

from app.openqasm3.visitor import LeqoTransformer


class ConnectVariables(LeqoTransformer[None]):
    """Connect variables based on specification."""

    conn_name_counter: int
    spec: list[list[str]]
    rename: dict[str, str]
    declared: dict[str, bool]

    def __init__(self, spec: list[list[str]]) -> None:
        """Accept and save the specification.

        The specification should of the following format:
        - one list of sub-lists
        - each sub-lists contains the names of all variables to connect
        """
        self.conn_name_counter = 0
        self.spec = spec
        self.rename = {}
        self.declared = {}

        for conn in spec:
            conn_name = self.new_conncetion_name()
            self.declared[conn_name] = False
            for qubit in conn:
                self.rename[qubit] = conn_name

    def new_conncetion_name(self) -> str:
        """Generate unique names for connections."""
        self.conn_name_counter += 1
        return f"connect{self.conn_name_counter}"

    def visit_Identifier(self, node: Identifier) -> Identifier:
        """Rename the identifier if in the rename dictionary."""
        name = node.name
        node.name = self.rename.get(name, name)
        return node

    def visit_QubitDeclaration(self, node: QubitDeclaration) -> QASMNode | None:
        """Ensure that connection-variables are only declared once."""
        name = node.qubit.name
        if name not in self.rename:
            return self.generic_visit(node)
        conn = self.rename[name]
        if self.declared[conn]:
            return None
        self.declared[conn] = True
        return self.generic_visit(node)

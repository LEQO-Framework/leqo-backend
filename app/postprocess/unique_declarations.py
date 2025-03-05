from typing import override

from openqasm3.ast import (
    ClassicalDeclaration,
    ConstantDeclaration,
    Identifier,
    QASMNode,
    QubitDeclaration,
)
from openqasm3.visitor import QASMTransformer


def new_name(name: str) -> str:
    """
    Create a new name, by adding a number or increasing an existing one.
    """
    i = len(name) - 1
    while name[i:].isdigit():
        i -= 1
    i += 1
    base = name[:i]
    raw_num = name[i:]
    num = int(raw_num) if raw_num != "" else 0
    return base + str(num + 1)


class UniqueDeclarations(QASMTransformer[None]):
    """
    This visitor removes duplicate declarations.
    It handles already seen declarations dependent on the type:
    ClassicalDeclaration: remove
    ConstantDeclaration: rename
    QubitDeclaration: remove
    """

    names: set[str]
    rename: dict[str, str]

    def __init__(self) -> None:
        self.names = set()
        self.rename = {}

    @override
    def generic_visit(self, node: QASMNode, context: None = None) -> QASMNode:
        """
        There was a bug in the openqasm3 QASMTransformer:
        It did not visited nodes that where in lists of lists.
        However, this required to find all occurences of an Identifier.
        Therefore we override the generic visit here to recursively search through lists.
        """
        for field, old_value in node.__dict__.items():
            if isinstance(old_value, list):
                self.list_visit(old_value)
            elif isinstance(old_value, QASMNode):
                new_node = (
                    self.visit(old_value, context) if context else self.visit(old_value)
                )
                if new_node is None:
                    delattr(node, field)
                else:
                    setattr(node, field, new_node)
        return node

    def list_visit(self, values: list[object]) -> None:
        """
        A helper function to recursively visit nodes in the AST.
        """
        new_values: list[object] = []
        for value in values:
            if isinstance(value, list):
                self.list_visit(value)
                new_values.append(value)
            elif isinstance(value, QASMNode):
                new_value = self.visit(value)
                if new_value is None:
                    continue
                if not isinstance(new_value, QASMNode):
                    new_values.extend(new_value)
                    continue
                new_values.append(new_value)
        values[:] = new_values

    def visit_Identifier(self, node: Identifier) -> QASMNode:
        """
        Rename the identifier, if declarations changed.
        """
        name = node.name
        if name in self.rename:
            node.name = self.rename[name]
        return self.generic_visit(node)

    def visit_ClassicalDeclaration(self, node: ClassicalDeclaration) -> QASMNode | None:
        """
        Check for duplicates, removing them.
        """
        name = node.identifier.name
        if name in self.names:
            return None
        self.names.add(name)
        return self.generic_visit(node)

    def visit_QubitDeclaration(self, node: QubitDeclaration) -> QASMNode | None:
        """
        Check for duplicates, removing them.
        """
        name = node.qubit.name
        if name in self.names:
            return None
        self.names.add(name)
        return self.generic_visit(node)

    def visit_ConstantDeclaration(self, node: ConstantDeclaration) -> QASMNode:
        """
        Check for duplicates, renaming them.
        """
        name = node.identifier.name
        if name in self.names:
            new = new_name(name)
            while new in self.names:
                new = new_name(new)
            node.identifier.name = new
            self.names.add(new)
            self.rename[name] = new
        else:
            self.names.add(name)
        return self.generic_visit(node)

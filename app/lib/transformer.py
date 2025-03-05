from typing import override

from openqasm3.ast import QASMNode
from openqasm3.visitor import QASMTransformer


class Transformer(QASMTransformer[None]):
    """
    This QASMTransformer child fixes an issue in the parent,
    where it was not recursively visiting lists in lists.
    This is important if visit_Identifier is used.
    """

    names: set[str]
    rename: dict[str, str]

    def __init__(self) -> None:
        self.names = set()
        self.rename = {}

    @override
    def generic_visit(self, node: QASMNode, context: None = None) -> QASMNode:
        """
        This is almost a clone of the parent generic_visit,
        but it handles lists recursively.
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
        A helper function to recursively visit lists in lists.
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
        values[:] = new_values  # modify the input inplace

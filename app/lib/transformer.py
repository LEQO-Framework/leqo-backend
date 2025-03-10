"""Fix QASMTransformer ignoring lists in lists and tuples."""

from typing import TypeVar, override

from openqasm3.ast import QASMNode
from openqasm3.visitor import QASMTransformer

T = TypeVar("T")


class Transformer(QASMTransformer[T]):
    """Fixes an issue in the parent, walk through lists/tuples recursively."""

    @override
    def generic_visit(self, node: QASMNode, context: T | None = None) -> QASMNode:
        """Almost a clone of the parent method, but handles lists/tuples recursively."""
        for field, old_value in node.__dict__.items():
            if isinstance(old_value, list):
                setattr(node, field, self.list_visit(old_value, context))
            elif isinstance(old_value, tuple):
                setattr(node, field, self.tuple_visit(old_value, context))
            elif isinstance(old_value, QASMNode):
                new_node = (
                    self.visit(old_value, context)
                    if context is not None
                    else self.visit(old_value)
                )
                if new_node is None:
                    delattr(node, field)
                else:
                    setattr(node, field, new_node)
        return node

    def list_visit(
        self,
        values: list[object],
        context: T | None,
    ) -> list[object]:
        """Recursively visits lists in lists."""
        new_values: list[object] = []
        for value in values:
            if isinstance(value, list):
                new_values.append(self.list_visit(value, context))
            elif isinstance(value, tuple):
                new_values.append(self.tuple_visit(value, context))
            elif isinstance(value, QASMNode):
                new_value = (
                    self.visit(value, context)
                    if context is not None
                    else self.visit(value)
                )
                if new_value is None:
                    continue
                if not isinstance(new_value, QASMNode):
                    new_values.extend(new_value)
                    continue
                new_values.append(new_value)
        return new_values

    def tuple_visit(
        self,
        values: tuple[object, ...],
        context: T | None,
    ) -> tuple[object, ...]:
        return tuple(self.list_visit(list(values), context))

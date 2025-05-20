"""
Helpers for renaming variables in an abstract syntax tree.
"""

from typing import TypeVar

from openqasm3.ast import Identifier, QASMNode

from app.openqasm3.visitor import LeqoTransformer


class _SimpleRenameTransformer(LeqoTransformer[None]):
    renames: dict[str, str]

    def __init__(self, renamings: dict[str, str]) -> None:
        super().__init__()
        self.renames = renamings

    def visit_Identifier(self, node: Identifier) -> Identifier:
        node.name = self.renames.get(node.name, node.name)
        return node


TNode = TypeVar("TNode", bound=QASMNode)


def simple_rename(node: TNode, renamings: dict[str, str]) -> TNode:
    """
    Renames variables in node according to the specified mapping.

    :param node: The node to rename variables in
    :param renamings: The variables to rename
    :return: The transformed nodec
    """
    return _SimpleRenameTransformer(renamings).visit(node)  # type: ignore

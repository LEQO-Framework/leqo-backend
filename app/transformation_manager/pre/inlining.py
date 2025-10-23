"""
Transformer to inline declarations.
"""

from openqasm3.ast import (
    ConstantDeclaration,
    Expression,
    Identifier,
    IntegerLiteral,
    IntType,
    UintType,
)

from app.openqasm3.visitor import LeqoTransformer
from app.transformation_manager.pre.utils import PreprocessingException


class InliningTransformer(LeqoTransformer[None]):
    """
    Inlines all integer :py:class:`openqasm3.ast.ConstantDeclaration` in a qasm ast.
    """

    lookup: dict[str, ConstantDeclaration]

    def __init__(self) -> None:
        self.lookup = {}

    def visit_ConstantDeclaration(
        self, node: ConstantDeclaration
    ) -> ConstantDeclaration | None:
        """
        Removes integer constants from the ast and saves them in a lookup table.
        """

        match node.type:
            case IntType() | UintType():
                pass
            case _:
                return node

        match node.init_expression:
            case IntegerLiteral():
                pass
            case _:
                return node

        if self.lookup.get(node.identifier.name) is not None:
            raise PreprocessingException("Constant already defined")

        self.lookup[node.identifier.name] = node
        return None  # Remove node

    def visit_Identifier(self, node: Identifier) -> Identifier | Expression:
        """
        Rewrites an identifier to use the inlined aliases.

        :param node: The identifier to process
        :return: The inlined value or unchanged node
        """

        replacement = self.lookup.get(node.name)
        if replacement is None:
            return node

        return replacement.init_expression

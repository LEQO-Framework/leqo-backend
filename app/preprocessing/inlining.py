from openqasm3.ast import (
    ConstantDeclaration,
    Expression,
    Identifier,
)
from openqasm3.visitor import QASMTransformer

from app.model.SectionInfo import SectionInfo


class InliningTransformer(QASMTransformer[SectionInfo]):
    """
    Inlines all :py:class:`openqasm3.ast.ConstantDeclaration` in a qasm ast.
    """

    lookup: dict[str, ConstantDeclaration]

    def __init__(self) -> None:
        self.lookup = {}

    def visit_ConstantDeclaration(
        self, node: ConstantDeclaration, _context: SectionInfo
    ) -> None:
        """
        Stores the const declaration and removes it from the ast.

        :param node: The statement to process
        :return: None to remove the alias statement
        """

        if self.lookup.get(node.identifier.name) is not None:
            raise Exception("Alias already defined")

        self.lookup[node.identifier.name] = node

    def visit_Identifier(
        self, node: Identifier, _context: SectionInfo
    ) -> Identifier | Expression:
        """
        Rewrites an identifier to use the inlined aliases.
        ToDo: We might change the type here: Is this a problem?

        :param node: The identifier to process
        :return: The inlined value or unchanged node
        """

        replacement = self.lookup.get(node.name)
        if replacement is None:
            return node

        return replacement.init_expression

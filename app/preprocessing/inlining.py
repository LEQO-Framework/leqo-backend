from openqasm3.ast import (
    AliasStatement,
    Concatenation,
    ConstantDeclaration,
    Expression,
    Identifier,
)
from openqasm3.visitor import QASMTransformer


class InliningTransformer(QASMTransformer[None]):
    """
    Inlines all :py:class:`openqasm3.ast.AliasStatement` in a qasm ast.
    """

    lookup: dict[str, AliasStatement | ConstantDeclaration]

    def __init__(self) -> None:
        self.lookup = {}

    def visit_AliasStatement(self, node: AliasStatement) -> None:
        """
        Stores the alias statement and removes it from the ast.

        :param node: The statement to process
        :return: None to remove the alias statement
        """

        if self.lookup.get(node.target.name) is not None:
            raise Exception("Alias already defined")

        self.lookup[node.target.name] = node

    def visit_ConstantDeclaration(self, node: ConstantDeclaration) -> None:
        if self.lookup.get(node.identifier.name) is not None:
            raise Exception("Alias already defined")

        self.lookup[node.identifier.name] = node

    def visit_Identifier(
        self, node: Identifier
    ) -> Identifier | Concatenation | Expression:
        """
        Rewrites an identifier to use the inlined aliases.
        ToDo: We might change the type here: Is this a problem?

        :param node: The identifier to process
        :return: The inlined value or unchanged node
        """

        replacement = self.lookup.get(node.name)
        if replacement is None:
            return node

        match replacement:
            case ConstantDeclaration():
                return replacement.init_expression
            case AliasStatement():
                return replacement.value

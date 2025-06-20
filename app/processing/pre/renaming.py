"""
Transformer to rename identifiers in a qasm program to globally unique names.
"""

from uuid import UUID

from openqasm3.ast import (
    AliasStatement,
    CalibrationDefinition,
    ClassicalDeclaration,
    ConstantDeclaration,
    ExternDeclaration,
    Identifier,
    IODeclaration,
    QASMNode,
    QuantumGateDefinition,
    QubitDeclaration,
    SubroutineDefinition,
)
from openqasm3.visitor import QASMTransformer

from app.processing.pre.utils import annotate


class RenameRegisterTransformer(QASMTransformer[UUID]):
    """
    Renames all declarations inside a qasm program to prevent collisions when merging.
    """

    renames: dict[str, Identifier]

    def __init__(self) -> None:
        self.renames = {}

    def new_identifier(self, old_identifier: Identifier, context: UUID) -> Identifier:
        """
        Generates a new identifier that will be globally unique even after merging multiple programs.
        Adds the old identifier to the list of renames.

        :param old_identifier: The old identifier to be renamed.
        :param context: The context of the current program.
        :return: A new globally unique identifier.
        """

        new_identifier = Identifier(f"leqo_{context.hex}_{old_identifier.name}")
        self.renames[old_identifier.name] = new_identifier

        return new_identifier

    def visit_ConstantDeclaration(
        self, node: ConstantDeclaration, context: UUID
    ) -> QASMNode:
        identifier = self.new_identifier(node.identifier, context)
        return self.generic_visit(
            annotate(
                ConstantDeclaration(node.type, identifier, node.init_expression),
                node.annotations,
            ),
            context,
        )

    def visit_AliasStatement(self, node: AliasStatement, context: UUID) -> QASMNode:
        identifier = self.new_identifier(node.target, context)
        return self.generic_visit(
            annotate(AliasStatement(identifier, node.value), node.annotations), context
        )

    def visit_QubitDeclaration(self, node: QubitDeclaration, context: UUID) -> QASMNode:
        identifier = self.new_identifier(node.qubit, context)
        return self.generic_visit(
            annotate(QubitDeclaration(identifier, node.size), node.annotations), context
        )

    def visit_QuantumGateDefinition(
        self, node: QuantumGateDefinition, context: UUID
    ) -> QASMNode:
        name = self.new_identifier(node.name, context)
        return self.generic_visit(
            annotate(
                QuantumGateDefinition(name, node.arguments, node.qubits, node.body),
                node.annotations,
            ),
            context,
        )

    def visit_ExternDeclaration(
        self, node: ExternDeclaration, context: UUID
    ) -> QASMNode:
        identifier = self.new_identifier(node.name, context)
        return self.generic_visit(
            annotate(
                ExternDeclaration(identifier, node.arguments, node.return_type),
                node.annotations,
            ),
            context,
        )

    def visit_ClassicalDeclaration(
        self, node: ClassicalDeclaration, context: UUID
    ) -> QASMNode:
        identifier = self.new_identifier(node.identifier, context)
        return self.generic_visit(
            annotate(
                ClassicalDeclaration(node.type, identifier, node.init_expression),
                node.annotations,
            ),
            context,
        )

    def visit_IODeclaration(self, node: IODeclaration, context: UUID) -> IODeclaration:
        identifier = self.new_identifier(node.identifier, context)
        return annotate(
            IODeclaration(node.io_identifier, node.type, identifier), node.annotations
        )

    def visit_CalibrationDefinition(
        self, node: CalibrationDefinition, context: UUID
    ) -> QASMNode:
        name = self.new_identifier(node.name, context)
        return self.generic_visit(
            annotate(
                CalibrationDefinition(
                    name, node.arguments, node.qubits, node.return_type, node.body
                ),
                node.annotations,
            ),
            context,
        )

    def visit_SubroutineDefinition(
        self, node: SubroutineDefinition, context: UUID
    ) -> QASMNode:
        name = self.new_identifier(node.name, context)
        return self.generic_visit(
            annotate(
                SubroutineDefinition(name, node.arguments, node.body, node.return_type),
                node.annotations,
            ),
            context,
        )

    # `ForInLoop` only declares variable inside a scope
    # => No collisions with other blocks but theoretically without renamed globals

    def visit_Identifier(self, node: Identifier, _context: UUID) -> Identifier:
        """
        Renames identifiers using the old declaration names.

        :param node: Identifier to rename
        :return: Modified identifier
        """

        new_identifier = self.renames.get(node.name)
        if new_identifier is None:
            return node

        return new_identifier

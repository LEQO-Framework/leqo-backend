from openqasm3.ast import (
    AliasStatement,
    CalibrationDefinition,
    ClassicalDeclaration,
    ExternDeclaration,
    Identifier,
    IODeclaration,
    QASMNode,
    QuantumGateDefinition,
    QuantumStatement,
    QubitDeclaration,
    Statement,
    SubroutineDefinition,
)
from openqasm3.visitor import QASMTransformer

from app.model.SectionInfo import SectionInfo
from app.preprocessing.utils import annotate


class RenameRegisterTransformer(QASMTransformer[SectionInfo]):
    """
    Renames all declarations inside a qasm program to prevent collisions when merging.
    """

    declarations: dict[str, Identifier]

    def __init__(self) -> None:
        self.declarations = {}

    def new_identifier(
        self, old_identifier: Identifier, context: SectionInfo
    ) -> Identifier:
        """
        Generates a new identifier that will be globally unique even after merging multiple programs.
        Adds the old identifier to the list of renames.

        :param old_identifier: The old identifier to be renamed.
        :param context: The context of the current program.
        :return: A new globally unique identifier.
        """

        if self.declarations.get(old_identifier.name) is not None:
            raise Exception("Variable already defined")

        index = len(self.declarations)
        identifier = Identifier(f"leqo_section{context.index}_declaration{index}")
        self.declarations[old_identifier.name] = identifier

        return identifier

    def visit_AliasStatement(
        self, node: AliasStatement, context: SectionInfo
    ) -> QASMNode:
        identifier = self.new_identifier(node.target, context)
        return self.generic_visit(
            annotate(AliasStatement(identifier, node.value), node.annotations), context
        )

    def visit_QubitDeclaration(
        self, node: QubitDeclaration, context: SectionInfo
    ) -> QubitDeclaration:
        identifier = self.new_identifier(node.qubit, context)
        return annotate(QubitDeclaration(identifier, node.size), node.annotations)

    def visit_QuantumGateDefinition(
        self, node: QuantumGateDefinition, context: SectionInfo
    ) -> QASMNode:
        body: list[QuantumStatement] = []
        for child in node.body:
            body.append(self.visit(child))

        name = self.new_identifier(node.name, context)
        return self.generic_visit(
            annotate(
                QuantumGateDefinition(name, node.arguments, node.qubits, body),
                node.annotations,
            ),
            context,
        )

    def visit_ExternDeclaration(
        self, node: ExternDeclaration, context: SectionInfo
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
        self, node: ClassicalDeclaration, context: SectionInfo
    ) -> QASMNode:
        identifier = self.new_identifier(node.identifier, context)
        return self.generic_visit(
            annotate(
                ClassicalDeclaration(node.type, identifier, node.init_expression),
                node.annotations,
            ),
            context,
        )

    def visit_IODeclaration(
        self, node: IODeclaration, context: SectionInfo
    ) -> IODeclaration:
        identifier = self.new_identifier(node.identifier, context)
        return annotate(
            IODeclaration(node.io_identifier, node.type, identifier), node.annotations
        )

    def visit_CalibrationDefinition(
        self, node: CalibrationDefinition, context: SectionInfo
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
        self, node: SubroutineDefinition, context: SectionInfo
    ) -> QASMNode:
        name = self.new_identifier(node.name, context)

        body: list[Statement] = []
        for child in node.body:
            body.append(self.visit(child))

        return self.generic_visit(
            annotate(
                SubroutineDefinition(name, node.arguments, body, node.return_type),
                node.annotations,
            ),
            context,
        )

    # `ForInLoop` only declares variable inside a scope
    # => No collisions with other blocks but theoretically without renamed globals

    def visit_Identifier(self, node: Identifier, _context: SectionInfo) -> Identifier:
        """
        Renames identifiers using the old declaration names.
        ToDo: We currently ignore scope!!

        :param node: Identifier to rename
        :return: Modified identifier
        """

        new_identifier = self.declarations.get(node.name)
        if new_identifier is None:
            return node

        return new_identifier

from openqasm3.ast import (
    AliasStatement,
    CalibrationDefinition,
    ClassicalDeclaration,
    ExternDeclaration,
    Identifier,
    IODeclaration,
    QuantumGateDefinition,
    QuantumStatement,
    QubitDeclaration,
    Statement,
    SubroutineDefinition,
)
from openqasm3.visitor import QASMTransformer

from app.model.SectionInfo import SectionInfo


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
    ) -> AliasStatement:
        identifier = self.new_identifier(node.target, context)
        return AliasStatement(identifier, node.value)

    def visit_QubitDeclaration(
        self, node: QubitDeclaration, context: SectionInfo
    ) -> QubitDeclaration:
        identifier = self.new_identifier(node.qubit, context)
        return QubitDeclaration(identifier, node.size)

    def visit_QuantumGateDefinition(
        self, node: QuantumGateDefinition, context: SectionInfo
    ) -> QuantumGateDefinition:
        body: list[QuantumStatement] = []
        for child in node.body:
            body.append(self.visit(child))

        name = self.new_identifier(node.name, context)
        return QuantumGateDefinition(name, node.arguments, node.qubits, body)

    def visit_ExternDeclaration(
        self, node: ExternDeclaration, context: SectionInfo
    ) -> ExternDeclaration:
        identifier = self.new_identifier(node.name, context)
        return ExternDeclaration(identifier, node.arguments, node.return_type)

    def visit_ClassicalDeclaration(
        self, node: ClassicalDeclaration, context: SectionInfo
    ) -> ClassicalDeclaration:
        identifier = self.new_identifier(node.identifier, context)
        return ClassicalDeclaration(node.type, identifier, node.init_expression)

    def visit_IODeclaration(
        self, node: IODeclaration, context: SectionInfo
    ) -> IODeclaration:
        identifier = self.new_identifier(node.identifier, context)
        return IODeclaration(node.io_identifier, node.type, identifier)

    def visit_CalibrationDefinition(
        self, node: CalibrationDefinition, context: SectionInfo
    ) -> CalibrationDefinition:
        name = self.new_identifier(node.name, context)
        return CalibrationDefinition(
            name, node.arguments, node.qubits, node.return_type, node.body
        )

    def visit_SubroutineDefinition(
        self, node: SubroutineDefinition, context: SectionInfo
    ) -> SubroutineDefinition:
        name = self.new_identifier(node.name, context)

        body: list[Statement] = []
        for child in node.body:
            body.append(self.visit(child))

        return SubroutineDefinition(name, node.arguments, body, node.return_type)

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

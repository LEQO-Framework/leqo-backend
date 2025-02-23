from openqasm3.ast import (
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


class RenameRegisterTransformer(QASMTransformer[None]):
    """
    Renames all declarations inside a qasm program to prevent collisions when merging.
    """

    stage_index: int
    declarations: dict[str, Identifier]

    def __init__(self, stage_index: int):
        self.stage_index = stage_index
        self.declarations = {}

    def new_identifier(self, old_identifier: Identifier) -> Identifier:
        if self.declarations.get(old_identifier.name) is not None:
            raise Exception("Variable already defined")

        index = len(self.declarations)
        identifier = Identifier(f"leqo_section{self.stage_index}_declaration{index}")
        self.declarations[old_identifier.name] = identifier

        return identifier

    def visit_QubitDeclaration(self, node: QubitDeclaration) -> QubitDeclaration:
        """
        Renames identifier of qubit declaration.

        :param node: Declaration to modify
        :return: Modified declaration
        """

        identifier = self.new_identifier(node.qubit)
        return QubitDeclaration(identifier, node.size)

    def visit_QuantumGateDefinition(
        self, node: QuantumGateDefinition
    ) -> QuantumGateDefinition:
        body: list[QuantumStatement] = []
        for child in node.body:
            body.append(self.visit(child))

        name = self.new_identifier(node.name)
        return QuantumGateDefinition(name, node.arguments, node.qubits, body)

    def visit_ExternDeclaration(self, node: ExternDeclaration) -> ExternDeclaration:
        identifier = self.new_identifier(node.name)
        return ExternDeclaration(identifier, node.arguments, node.return_type)

    def visit_ClassicalDeclaration(
        self, node: ClassicalDeclaration
    ) -> ClassicalDeclaration:
        """
        Renames identifier of classical declaration.

        :param node: Declaration to modify
        :return: Modified declaration
        """

        identifier = self.new_identifier(node.identifier)
        return ClassicalDeclaration(node.type, identifier, node.init_expression)

    def visit_IODeclaration(self, node: IODeclaration) -> IODeclaration:
        identifier = self.new_identifier(node.identifier)
        return IODeclaration(node.io_identifier, node.type, identifier)

    def visit_CalibrationDefinition(
        self, node: CalibrationDefinition
    ) -> CalibrationDefinition:
        name = self.new_identifier(node.name)
        return CalibrationDefinition(
            name, node.arguments, node.qubits, node.return_type, node.body
        )

    def visit_SubroutineDefinition(
        self, node: SubroutineDefinition
    ) -> SubroutineDefinition:
        name = self.new_identifier(node.name)

        body: list[Statement] = []
        for child in node.body:
            body.append(self.visit(child))

        return SubroutineDefinition(name, node.arguments, body, node.return_type)

    # `ForInLoop` only declares variable inside a scope
    # => No collisions with other blocks but theoretically without renamed globals

    def visit_Identifier(self, node: Identifier) -> Identifier:
        """
        Renames identifiers using the old declaration names.

        :param node: Identifier to rename
        :return: Modified identifier
        """

        new_identifier = self.declarations.get(node.name)
        if new_identifier is None:
            return node

        return new_identifier

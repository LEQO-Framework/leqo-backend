from openqasm3.ast import (
    Box,
    BranchingStatement,
    CompoundStatement,
    DurationOf,
    ForInLoop,
    Identifier,
    IntegerLiteral,
    Pragma,
    Program,
    QASMNode,
    QuantumGate,
    QuantumGateDefinition,
    QuantumStatement,
    QubitDeclaration,
    Statement,
    SubroutineDefinition,
    WhileLoop,
)
from openqasm3.visitor import QASMTransformer


class SplitRegAndIOParse(QASMTransformer[None]):
    redeclared: dict[str, int]

    def __init__(self) -> None:
        self.redeclared = {}

    # helper functions
    @staticmethod
    def generate_names(name: str, amount: int) -> list[str]:
        return [f"{name}_part{i}" for i in range(amount)]

    @staticmethod
    def add_to_statement_list(
        statements: list[Statement] | list[Statement | Pragma],
        target: QASMNode,
        replacements: list[Statement],
    ) -> None:
        for i, v in enumerate(statements):
            if v == target:
                del replacements[i]
                for replacement in reversed(replacements):
                    statements.insert(i, replacement)
                return

    def split_qubits(
        self,
        statements: list[Statement | Pragma] | list[Statement] | list[QuantumStatement],
    ) -> None:
        if isinstance(statements, list[Statement | Pragma] | list[Statement]):
            self.split_qubit_reg_declaration(statements)
        self.split_qubit_reg_gates(statements)

    def split_qubit_reg_gates(
        self,
        statements: list[Statement | Pragma] | list[Statement] | list[QuantumStatement],
    ) -> None:
        to_replace: list[tuple[QubitDeclaration, list[QubitDeclaration]]] = []
        for node in statements:
            if isinstance(node, QuantumGate):
                qubits = node.qubits

    def split_qubit_reg_declaration(
        self,
        statements: list[Statement | Pragma] | list[Statement],
    ) -> None:
        to_replace: list[tuple[QubitDeclaration, list[QubitDeclaration]]] = []
        for node in statements:
            if isinstance(node, QubitDeclaration):
                size = node.size
                if size is None:
                    return
                if not isinstance(size, IntegerLiteral):
                    msg = f"Unsupported type in QubitDeclaration.size: {type(size)}"
                    raise TypeError(msg)
                value = size.value
                name = node.qubit.name
                names = self.generate_names(name, value)
                self.redeclared[name] = value
                replacements: list[QubitDeclaration] = [
                    QubitDeclaration(qubit=Identifier(name), size=None)
                    for name in names
                ]
                to_replace.append((node, replacements))
        for node, replacements in to_replace:
            i = statements.index(node)
            del statements[i]
            for j, replacement in enumerate(replacements):
                statements.insert(i + j, replacement)
        return

    # visitors
    def visit_Program(self, node: Program) -> QASMNode:
        self.split_qubits(node.statements)
        return self.generic_visit(node)

    def visit_CompoundStatement(self, node: CompoundStatement) -> QASMNode:
        self.split_qubits(node.statements)
        return self.generic_visit(node)

    def visit_SubroutineDefinition(self, node: SubroutineDefinition) -> QASMNode:
        self.split_qubits(node.body)
        return self.generic_visit(node)

    def visit_WhileLoop(self, node: WhileLoop) -> QASMNode:
        self.split_qubits(node.block)
        return self.generic_visit(node)

    def visit_ForInLoop(self, node: ForInLoop) -> QASMNode:
        self.split_qubits(node.block)
        return self.generic_visit(node)

    def visit_DurationOf(self, node: DurationOf) -> QASMNode:
        self.split_qubits(node.target)
        return self.generic_visit(node)

    def visit_QuantumGateDefinition(self, node: QuantumGateDefinition) -> QASMNode:
        self.split_qubits(node.body)
        return self.generic_visit(node)

    def visit_Box(self, node: Box) -> QASMNode:
        self.split_qubits(node.body)
        return self.generic_visit(node)

    def visit_BranchingStatement(self, node: BranchingStatement) -> QASMNode:
        self.split_qubits(node.if_block)
        self.split_qubits(node.else_block)
        return self.generic_visit(node)

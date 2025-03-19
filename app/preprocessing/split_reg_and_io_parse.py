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
    QuantumGateDefinition,
    QubitDeclaration,
    Statement,
    SubroutineDefinition,
    WhileLoop,
)
from openqasm3.visitor import QASMTransformer


class SplitRegAndIOParse(QASMTransformer[None]):
    # helper functions
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
                replacements: list[QubitDeclaration] = [
                    QubitDeclaration(qubit=Identifier(f"{name}_part{i}"), size=None)
                    for i in range(value)
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
        self.split_qubit_reg_declaration(node.statements)
        return self.generic_visit(node)

    def visit_CompoundStatement(self, node: CompoundStatement) -> QASMNode:
        self.split_qubit_reg_declaration(node.statements)
        return self.generic_visit(node)

    def visit_SubroutineDefinition(self, node: SubroutineDefinition) -> QASMNode:
        self.split_qubit_reg_declaration(node.body)
        return self.generic_visit(node)

    def visit_WhileLoop(self, node: WhileLoop) -> QASMNode:
        self.split_qubit_reg_declaration(node.block)
        return self.generic_visit(node)

    def visit_ForInLoop(self, node: ForInLoop) -> QASMNode:
        self.split_qubit_reg_declaration(node.block)
        return self.generic_visit(node)

    def visit_DurationOf(self, node: DurationOf) -> QASMNode:
        self.split_qubit_reg_declaration(node.target)
        return self.generic_visit(node)

    def visit_QuantumGateDefinition(self, node: QuantumGateDefinition) -> QASMNode:
        self.split_qubit_reg_declaration(node.body)
        return self.generic_visit(node)

    def visit_Box(self, node: Box) -> QASMNode:
        self.split_qubit_reg_declaration(node.body)
        return self.generic_visit(node)

    def visit_BranchingStatement(self, node: BranchingStatement) -> QASMNode:
        self.split_qubit_reg_declaration(node.if_block)
        self.split_qubit_reg_declaration(node.else_block)
        return self.generic_visit(node)

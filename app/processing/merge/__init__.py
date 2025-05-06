"""Merge all nodes of the :class:`app.processing.graph.ProgramGraph` into a single QASM program."""

from copy import deepcopy
from io import UnsupportedOperation

from networkx import topological_sort
from openqasm3.ast import (
    AliasStatement,
    Annotation,
    BranchingStatement,
    Concatenation,
    Expression,
    Identifier,
    IntegerLiteral,
    Pragma,
    Program,
    QASMNode,
    QubitDeclaration,
    Statement,
)

from app.openqasm3.ast import CommentStatement
from app.openqasm3.visitor import LeqoTransformer
from app.processing.graph import ProcessedProgramNode, ProgramGraph
from app.processing.merge.connections import connect_qubits
from app.processing.post import postprocess
from app.processing.utils import cast_to_program

GLOBAL_REG_NAME = "leqo_reg"


class RemoveAnnotationTransformer(LeqoTransformer[None]):
    to_delete: set[str]

    def __init__(self, inputs: bool, outputs: bool) -> None:
        self.to_delete = {"leqo.reusable", "leqo.uncompute", "leqo.dirty"}
        if inputs:
            self.to_delete.add("leqo.input")
        if outputs:
            self.to_delete.add("leqo.output")

    def visit_Annotation(self, node: Annotation) -> QASMNode | None:
        if node.keyword.strip().split()[0] in self.to_delete:
            return None
        return node


def merge_if_nodes(
    if_node: ProcessedProgramNode,
    endif_node: ProcessedProgramNode,
    then_graph: ProgramGraph,
    else_graph: ProgramGraph,
    condition: Expression,
) -> Program:
    endif_node_from_else = deepcopy(endif_node)
    else_graph.node_data[endif_node.raw] = endif_node_from_else

    reg_name = f"leqo_{if_node.id.hex}_if_reg"
    then_size = connect_qubits(then_graph, reg_name, if_node)
    else_size = connect_qubits(else_graph, reg_name, if_node)

    if endif_node != endif_node_from_else:
        msg = "Unsupported: output of 'then' does not match with output of 'else'"
        raise UnsupportedOperation(msg)

    all_statements = cast_to_program(
        RemoveAnnotationTransformer(inputs=False, outputs=True).visit(
            if_node.implementation,
        ),
    ).statements

    required_size = max(then_size, else_size)
    input_size = sum([len(ids) for ids in if_node.qubit.declaration_to_ids.values()])
    ancillae_size = required_size - input_size
    if ancillae_size > 0:
        all_statements.append(
            QubitDeclaration(
                Identifier(f"leqo_{if_node.id.hex}_ancillae"),
                IntegerLiteral(ancillae_size),
            ),
        )

    declarations = [d for d in all_statements if isinstance(d, QubitDeclaration)]
    if len(declarations) == 1:
        all_statements.append(
            AliasStatement(Identifier(reg_name), declarations[0].qubit),
        )
    else:
        concat = Concatenation(
            declarations[0].qubit,
            declarations[1].qubit,
        )
        for i in range(2, len(declarations)):
            concat = Concatenation(concat, declarations[i].qubit)
        all_statements.append(
            AliasStatement(Identifier(reg_name), concat),
        )

    if_statements = []
    for node in topological_sort(then_graph):
        if node in [if_node.raw, endif_node.raw]:
            continue
        processed = then_graph.get_data_node(node)
        implementation = cast_to_program(
            RemoveAnnotationTransformer(True, True).visit(
                processed.implementation,
            ),
        )
        for statement in implementation.statements:
            if isinstance(statement, Pragma):
                continue
            if_statements.append(statement)

    else_statements = []
    for node in topological_sort(else_graph):
        if node in [if_node.raw, endif_node.raw]:
            continue
        processed = else_graph.get_data_node(node)
        implementation = cast_to_program(
            RemoveAnnotationTransformer(True, True).visit(
                processed.implementation,
            ),
        )
        for statement in implementation.statements:
            if isinstance(statement, Pragma):
                continue
            else_statements.append(statement)

    all_statements.append(
        BranchingStatement(
            condition,
            if_statements,
            else_statements,
        ),
    )
    all_statements.extend(
        cast_to_program(
            RemoveAnnotationTransformer(inputs=True, outputs=False).visit(
                endif_node.implementation,
            ),
        ).statements,
    )
    return Program(all_statements, version="3.1")


def merge_nodes(graph: ProgramGraph) -> Program:
    """Create a unified :class:`openqasm3.ast.Program` from a modelled graph with attached qasm implementation snippets.

    :param graph: Graph of all nodes representing the program
    :return: The unified qasm program
    """
    reg_size = connect_qubits(graph, GLOBAL_REG_NAME)

    all_statements: list[Statement | Pragma] = [
        QubitDeclaration(Identifier(GLOBAL_REG_NAME), IntegerLiteral(reg_size)),
    ]

    for node in topological_sort(graph):
        all_statements.append(CommentStatement(f"Start node {node.name}"))

        all_statements.extend(graph.get_data_node(node).implementation.statements)

        all_statements.append(CommentStatement(f"End node {node.name}"))

    merged_program = Program(all_statements, version="3.1")
    return postprocess(merged_program)

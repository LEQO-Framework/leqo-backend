"""Merge all nodes from :class:`app.processing.graph.ProgramGraph` into a single QASM program."""

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
from app.processing.graph import (
    ProgramGraph,
    ProgramNode,
)
from app.processing.merge.connections import connect_qubits
from app.processing.utils import cast_to_program

GLOBAL_REG_NAME = "leqo_reg"
IF_REG_NAME = "if_reg"
ANCILLAES_NAME = "ancillae"
OPENQASM_VERSION = "3.1"


class RemoveAnnotationTransformer(LeqoTransformer[None]):
    """Remove leqo annotations of specified types.

    :param inputs: Whether to remove 'leqo.input' annotations.
    :param outputs: Whether to remove 'leqo.output' annotations.
    """

    to_delete: set[str]

    def __init__(self, inputs: bool, outputs: bool) -> None:
        self.to_delete = {"leqo.reusable", "leqo.uncompute", "leqo.dirty"}
        if inputs:
            self.to_delete.add("leqo.input")
        if outputs:
            self.to_delete.add("leqo.output")

    def visit_Annotation(self, node: Annotation) -> QASMNode | None:
        """Remove or keep annotation."""
        if node.keyword.strip().split()[0] in self.to_delete:
            return None
        return node


def graph_to_statements(
    graph: ProgramGraph,
    if_node: ProgramNode,
    endif_node: ProgramNode,
) -> list[Statement]:
    """Concatenate nodes from graph via topological_sort and remove annotations.

    **if_node** and **endif_node** need to be skipped here.
    """
    result = []
    for node in topological_sort(graph):
        if node in [if_node, endif_node]:
            continue
        processed = graph.get_data_node(node)
        implementation = cast_to_program(
            RemoveAnnotationTransformer(True, True).visit(
                processed.implementation,
            ),
        )
        for statement in implementation.statements:
            if isinstance(statement, Pragma):
                msg = f"Can't handle pragma inside if-else: {statement}"
                raise UnsupportedOperation(msg)
            result.append(statement)
    return result


def merge_if_nodes(
    if_node_raw: ProgramNode,
    endif_node_raw: ProgramNode,
    then_graph: ProgramGraph,
    else_graph: ProgramGraph,
    condition: Expression,
) -> tuple[Program, int]:
    """Construct single Program with a :class:`openqasm3.ast.BranchingStatement` from two sub-graphs.

    There are two known limitations of this implementation:

    - Classical outputs are not supported.
        This is because :class:`openqasm3.ast.AliasStatement` are scoped inside the if-else,
        meaning they can not pass there value to the **endif_node**, which is outside.
        This would be required for classical outputs to work.
        However, classical input can be used.

    - The **endif_node** from both **then_graph** and **else_graph** need to match.
        This not only true for the size of the outputs, but also for the order of the used qubit ids.

    :param if_node: The border node that leads into the if-else.
        This node has to be in both **then_graph** and **else_graph**.
    :param endif_node: The border node that leads out of the if-else.
        This node has to be in both **then_graph** and **else_graph**.
    :param then_graph: The sub-graph for the **then** case.
    :param else_graph: The sub-graph for the **else** case.
    :param condition: The condition to use in the generated :class:`openqasm3.ast.BranchingStatement`.
    """
    if_node = then_graph.node_data[if_node_raw]
    endif_node = then_graph.node_data[endif_node_raw]
    assert if_node == else_graph.node_data[if_node_raw]
    assert endif_node == else_graph.node_data[endif_node_raw]

    endif_node_in_else = deepcopy(endif_node)
    else_graph.node_data[endif_node_raw] = endif_node_in_else

    reg_name = f"leqo_{if_node.id.hex}_{IF_REG_NAME}"
    then_size = connect_qubits(then_graph, reg_name, if_node)
    else_size = connect_qubits(else_graph, reg_name, if_node)

    if endif_node != endif_node_in_else:
        # NOTE: in the future, this should do something smarter
        msg = "Future Work: output of 'then' does not match with output of 'else'"
        raise NotImplementedError(msg)

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
                Identifier(f"leqo_{if_node.id.hex}_{ANCILLAES_NAME}"),
                IntegerLiteral(ancillae_size),
            ),
        )

    concat: Identifier | Concatenation | None = None
    for declaration in [d for d in all_statements if isinstance(d, QubitDeclaration)]:
        if concat is None:
            concat = declaration.qubit
        else:
            concat = Concatenation(concat, declaration.qubit)
    if concat is not None:  # concat == None means there are no qubits at all
        all_statements.append(
            AliasStatement(Identifier(reg_name), concat),
        )

    all_statements.append(
        BranchingStatement(
            condition,
            graph_to_statements(then_graph, if_node.raw, endif_node.raw),
            graph_to_statements(else_graph, if_node.raw, endif_node.raw),
        ),
    )
    all_statements.extend(
        cast_to_program(
            RemoveAnnotationTransformer(inputs=True, outputs=False).visit(
                endif_node.implementation,
            ),
        ).statements,
    )
    return Program(all_statements, version=OPENQASM_VERSION), required_size


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

    return Program(all_statements, version=OPENQASM_VERSION)

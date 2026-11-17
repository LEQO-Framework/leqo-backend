"""
Utils for nested-node processing.
"""

from openqasm3.ast import (
    AliasStatement,
    Annotation,
    ClassicalDeclaration,
    Identifier,
    IntegerLiteral,
    Pragma,
    Program,
    QubitDeclaration,
    Statement,
)

from app.model.CompileRequest import Edge, NestedBlock
from app.model.data_types import ClassicalType, LeqoSupportedType, QubitType
from app.transformation_manager.pre import converter


def generate_pass_node_implementation(
    requested_inputs: dict[int, LeqoSupportedType],
) -> Program:
    """
    Generate implementation for a so called pass node.

    The pass node just returns all input it gets as outputs.
    Similar to the python pass statement, it does not modify them.
    This is used as border nodes of the if-then-else.

    :param requested_inputs: The inputs to generate this from.
    :return: The implementation as an AST.
    """
    statements: list[Statement | Pragma] = []

    out_size = 0
    for index, input_type in requested_inputs.items():
        declaration_identifier = Identifier(f"pass_node_declaration_{index}")
        declaration: QubitDeclaration | ClassicalDeclaration
        match input_type:
            case QubitType():
                out_size += 1 if input_type.size is None else input_type.size
                declaration = QubitDeclaration(
                    declaration_identifier,
                    None
                    if input_type.size is None
                    else IntegerLiteral(input_type.size),
                )
            case ClassicalType():
                declaration = ClassicalDeclaration(
                    input_type.to_ast(),
                    declaration_identifier,
                    None,
                )
        declaration.annotations = [Annotation("leqo.input", str(index))]
        statements.append(declaration)
        alias = AliasStatement(
            Identifier(f"pass_node_alias_{index}"), declaration_identifier
        )
        alias.annotations = [Annotation("leqo.output", str(index))]
        statements.append(alias)

    return Program(statements, version=converter.TARGET_QASM_VERSION)


def generate_missing_qubit_pass_throughs(
    block: NestedBlock,
    node_id: str,
    requested_inputs: dict[int, LeqoSupportedType],
) -> list[Edge]:
    """
    Generate identity edges for the qubit inputs a nested block doesn't route out.

    The frontend modeler can't draw a node-less pass-through inside a nested block,
    so a qubit without such an edge would leave the node as a freshly allocated one.

    :param block: The nested block to check.
    :param node_id: The id of the node the block belongs to.
    :param requested_inputs: The inputs of that node.
    :return: An edge from each unrouted qubit input to the output with the same index.
    """
    qubit_ports = {
        index
        for index, input_type in requested_inputs.items()
        if isinstance(input_type, QubitType)
    }
    routed_out = {e.target[1] for e in block.edges if e.target[0] == node_id}
    return [
        Edge(source=(node_id, port), target=(node_id, port))
        for port in sorted(qubit_ports - routed_out)
    ]

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

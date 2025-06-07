from collections.abc import Callable, Coroutine, Iterable
from typing import Any

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

from app.converter import qasm_converter
from app.model.CompileRequest import (
    Edge,
    IfThenElseNode,
    ImplementationNode,
)
from app.model.CompileRequest import (
    Node as FrontendNode,
)
from app.model.data_types import ClassicalType, LeqoSupportedType, QubitType
from app.openqasm3.printer import leqo_dumps
from app.openqasm3.rename import simple_rename
from app.processing.condition import parse_condition
from app.processing.converted_graph import ConvertedProgramGraph
from app.processing.graph import ProgramNode
from app.processing.merge import merge_if_nodes
from app.processing.post import postprocess


def get_pass_node_impl(requested_inputs: dict[int, LeqoSupportedType]) -> Program:
    """Generate implementation for a so called pass node.

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
                out_size += input_type.reg_size
                declaration = QubitDeclaration(
                    declaration_identifier,
                    IntegerLiteral(input_type.reg_size),
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

    return Program(statements, version=qasm_converter.TARGET_QASM_VERSION)


async def enrich_if_else(
    node: IfThenElseNode,
    requested_inputs: dict[int, LeqoSupportedType],
    frontend_name_to_index: dict[str, int],
    build_graph: Callable[
        [Iterable[FrontendNode], Iterable[Edge]],
        Coroutine[Any, Any, ConvertedProgramGraph],
    ],
) -> ImplementationNode:
    """Generate implementation for if-then-else-node.

    :param node: The IfThenElseNode to generate the implementation for.
    :param requested_inputs: The inputs into that IfThenElseNode.
    :param frontend_name_to_index: Dict that points names used in frontend to inputs indexes.
    :param build_graph: Dependency injection for getting enrichments of the nested graphs.
    :return: The generated implementation.
    """
    parent_id = ProgramNode(node.id).id

    pass_node_impl = leqo_dumps(get_pass_node_impl(requested_inputs))
    if_id = f"leqo_{parent_id.hex}_if"
    if_node = ProgramNode(if_id)
    if_front_node = ImplementationNode(id=if_id, implementation=pass_node_impl)
    endif_id = f"leqo_{parent_id.hex}_endif"
    endif_node = ProgramNode(endif_id)
    endif_front_node = ImplementationNode(id=endif_id, implementation=pass_node_impl)

    for nested_block in (node.thenBlock, node.elseBlock):
        for edge in nested_block.edges:
            if edge.source[0] == node.id:
                edge.source = (if_front_node.id, edge.source[1])
            if edge.target[0] == node.id:
                edge.target = (endif_front_node.id, edge.target[1])

    then_graph = await build_graph(
        (*node.thenBlock.nodes, if_front_node, endif_front_node), node.thenBlock.edges
    )
    else_graph = await build_graph(
        (*node.elseBlock.nodes, if_front_node, endif_front_node), node.elseBlock.edges
    )

    condition = parse_condition(node.condition)
    renames = {}
    for identifier, index in frontend_name_to_index.items():
        renames[identifier] = then_graph.node_data[if_node].io.inputs[index].name
    condition = simple_rename(condition, renames)

    implementation, out_size = merge_if_nodes(
        if_node,
        endif_node,
        then_graph,
        else_graph,
        condition,
    )
    implementation = postprocess(implementation)
    return ImplementationNode(
        id=node.id,
        implementation=leqo_dumps(implementation),
    )

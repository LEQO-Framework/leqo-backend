"""Enrich the if-then-else node.

The core logic is in :func:`app.processing.merge.merge_if_nodes`,
this module calls this function and handles the extensive pre- and postprocessing.
"""

from collections.abc import Callable, Coroutine, Iterable
from copy import deepcopy
from typing import Any

from openqasm3.ast import (
    BranchingStatement,
    Expression,
)
from openqasm3.parser import parse

from app.enricher import ParsedImplementationNode
from app.model.CompileRequest import (
    Edge,
    IfThenElseNode,
)
from app.model.CompileRequest import (
    Node as FrontendNode,
)
from app.model.data_types import LeqoSupportedType
from app.openqasm3.rename import simple_rename
from app.processing.graph import ProgramGraph, ProgramNode
from app.processing.merge import merge_if_nodes
from app.processing.nested.utils import generate_pass_node_implementation
from app.processing.post import postprocess


def parse_condition(value: str) -> Expression:
    """Parse condition used in if-then-else.

    It uses a simple wrapper to leverage the parser provided by openqasm3.

    :param value: condition string from the frontend
    :return: parsed expression in AST
    """
    if_then_else_ast = parse(f"if({value}) {{}}").statements[0]
    if not isinstance(if_then_else_ast, BranchingStatement):
        raise RuntimeError()
    return if_then_else_ast.condition


async def enrich_if_then_else(
    node: IfThenElseNode,
    requested_inputs: dict[int, LeqoSupportedType],
    frontend_name_to_index: dict[str, int],
    build_graph: Callable[
        [Iterable[FrontendNode | ParsedImplementationNode], Iterable[Edge]],
        Coroutine[Any, Any, ProgramGraph],
    ],
) -> ParsedImplementationNode:
    """Generate implementation for if-then-else-node.

    :param node: The IfThenElseNode to generate the implementation for.
    :param requested_inputs: The inputs into that IfThenElseNode.
    :param frontend_name_to_index: Dict that points names used in frontend to inputs indexes.
    :param build_graph: Dependency injection for getting enrichments of the nested graphs.
    :return: The generated implementation.
    """
    parent_id = ProgramNode(node.id).id

    pass_node_impl = generate_pass_node_implementation(requested_inputs)
    if_id = f"leqo_{parent_id.hex}_if"
    if_node = ProgramNode(if_id)
    if_front_node = ParsedImplementationNode(
        id=if_id, implementation=deepcopy(pass_node_impl)
    )
    endif_id = f"leqo_{parent_id.hex}_endif"
    endif_node = ProgramNode(endif_id)
    endif_front_node = ParsedImplementationNode(
        id=endif_id, implementation=pass_node_impl
    )

    for nested_block in (node.thenBlock, node.elseBlock):
        for edge in nested_block.edges:
            if edge.source[0] == node.id:
                edge.source = (if_front_node.id, edge.source[1])
            if edge.target[0] == node.id:
                edge.target = (endif_front_node.id, edge.target[1])

    then_graph = await build_graph(
        (*node.thenBlock.nodes, deepcopy(if_front_node), deepcopy(endif_front_node)),
        node.thenBlock.edges,
    )
    else_graph = await build_graph(
        (*node.elseBlock.nodes, if_front_node, endif_front_node), node.elseBlock.edges
    )

    condition = parse_condition(node.condition)
    renames = {}
    for identifier, index in frontend_name_to_index.items():
        renames[identifier] = then_graph.node_data[if_node].io.inputs[index].name
    condition = simple_rename(condition, renames)

    implementation, _out_size = merge_if_nodes(
        if_node,
        endif_node,
        then_graph,
        else_graph,
        condition,
    )
    implementation = postprocess(implementation)
    return ParsedImplementationNode(
        id=node.id,
        implementation=implementation,
    )

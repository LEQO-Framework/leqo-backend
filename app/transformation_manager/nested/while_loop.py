"""
Enrich the while-loop node.
"""

from collections.abc import Callable, Coroutine
from copy import deepcopy
from typing import Any

from openqasm3.ast import Expression, WhileLoop
from openqasm3.parser import parse

from app.enricher import ParsedImplementationNode
from app.model.CompileRequest import WhileNode
from app.model.data_types import LeqoSupportedType
from app.openqasm3.rename import simple_rename
from app.transformation_manager.frontend_graph import FrontendGraph
from app.transformation_manager.graph import ProgramGraph, ProgramNode
from app.transformation_manager.merge import merge_while_nodes
from app.transformation_manager.nested.utils import generate_pass_node_implementation
from app.transformation_manager.post import postprocess


def parse_condition(value: str) -> Expression:
    """
    Parse condition used in while loop.
    """
    while_ast = parse(f"while({value}) {{}}").statements[0]
    if not isinstance(while_ast, WhileLoop):
        raise RuntimeError("Failed to parse while condition.")
    return while_ast.while_condition


async def enrich_while_loop(
    node: WhileNode,
    requested_inputs: dict[int, LeqoSupportedType],
    frontend_name_to_index: dict[str, int],
    build_graph: Callable[[FrontendGraph], Coroutine[Any, Any, ProgramGraph]],
) -> ParsedImplementationNode:
    """
    Generate implementation for while-loop node.
    """
    parent_id = ProgramNode(node.id).id

    pass_node_impl = generate_pass_node_implementation(requested_inputs)
    while_id = f"leqo_{parent_id.hex}_while"
    while_node = ProgramNode(while_id)
    while_front_node = ParsedImplementationNode(
        id=while_id, implementation=deepcopy(pass_node_impl)
    )
    endwhile_id = f"leqo_{parent_id.hex}_endwhile"
    endwhile_node = ProgramNode(endwhile_id)
    endwhile_front_node = ParsedImplementationNode(
        id=endwhile_id, implementation=pass_node_impl
    )

    for edge in node.block.edges:
        if edge.source[0] == node.id:
            edge.source = (while_front_node.id, edge.source[1])
        if edge.target[0] == node.id:
            edge.target = (endwhile_front_node.id, edge.target[1])

    loop_graph = await build_graph(
        FrontendGraph.create(
            (*node.block.nodes, while_front_node, endwhile_front_node),
            node.block.edges,
        )
    )

    condition = parse_condition(node.condition)
    renames = {}
    for identifier, index in frontend_name_to_index.items():
        renames[identifier] = loop_graph.node_data[while_node].io.inputs[index].name
    condition = simple_rename(condition, renames)

    implementation, _out_size = merge_while_nodes(
        while_node,
        endwhile_node,
        loop_graph,
        condition,
    )
    implementation = postprocess(implementation)
    return ParsedImplementationNode(
        id=node.id,
        implementation=implementation,
    )
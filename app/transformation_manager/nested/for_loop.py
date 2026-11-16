"""
Enrich the for-loop node.
"""

from collections.abc import Callable, Coroutine
from copy import deepcopy
from typing import Any

from openqasm3.ast import Identifier, IntegerLiteral, RangeDefinition

from app.enricher import ParsedImplementationNode
from app.model.CompileRequest import ForNode
from app.model.data_types import LeqoSupportedType
from app.transformation_manager.frontend_graph import FrontendGraph
from app.transformation_manager.graph import ProgramGraph, ProgramNode
from app.transformation_manager.merge import merge_for_nodes
from app.transformation_manager.nested.utils import generate_pass_node_implementation
from app.transformation_manager.post import postprocess


async def enrich_for_loop(
    node: ForNode,
    requested_inputs: dict[int, LeqoSupportedType],
    frontend_name_to_index: dict[str, int],
    build_graph: Callable[[FrontendGraph], Coroutine[Any, Any, ProgramGraph]],
) -> ParsedImplementationNode:
    """
    Generate implementation for for-loop node.
    """
    parent_id = ProgramNode(node.id).id

    pass_node_impl = generate_pass_node_implementation(requested_inputs)
    for_id = f"leqo_{parent_id.hex}_for"
    for_prog_node = ProgramNode(for_id)
    for_front_node = ParsedImplementationNode(
        id=for_id, implementation=deepcopy(pass_node_impl)
    )
    endfor_id = f"leqo_{parent_id.hex}_endfor"
    endfor_prog_node = ProgramNode(endfor_id)
    endfor_front_node = ParsedImplementationNode(
        id=endfor_id, implementation=pass_node_impl
    )

    for edge in node.block.edges:
        if edge.source[0] == node.id:
            edge.source = (for_front_node.id, edge.source[1])
        if edge.target[0] == node.id:
            edge.target = (endfor_front_node.id, edge.target[1])

    loop_graph = await build_graph(
        FrontendGraph.create(
            (*node.block.nodes, for_front_node, endfor_front_node),
            node.block.edges,
        )
    )

    iterator_id = Identifier(node.iterator)
    range_def = RangeDefinition(
        start=IntegerLiteral(node.range_start),
        end=IntegerLiteral(node.range_end),
        step=IntegerLiteral(node.step) if node.step != 1 else None
    )

    implementation, _out_size = merge_for_nodes(
        for_prog_node,
        endfor_prog_node,
        loop_graph,
        iterator_id,
        range_def
    )
    implementation = postprocess(implementation)
    return ParsedImplementationNode(
        id=node.id,
        implementation=implementation,
    )
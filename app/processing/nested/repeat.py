"""
Unroll the repeat node.
"""

from copy import deepcopy
from io import UnsupportedOperation

from app.enricher import ParsedImplementationNode
from app.model.CompileRequest import RepeatNode
from app.model.data_types import LeqoSupportedType
from app.processing.frontend_graph import FrontendGraph
from app.processing.graph import ProgramNode
from app.processing.nested.utils import generate_pass_node_implementation


def unroll_repeat(
    node: RepeatNode, requested_inputs: dict[int, LeqoSupportedType]
) -> tuple[str, str, FrontendGraph]:
    """
    Unroll and enrich the repeat node.

    :param node: The node to enrich
    :param requested_inputs: The inputs for that node
    :return: The unrolled + enriched graph and the border nodes of this graph
    """
    if node.iterations < 1:  # should have been checked by fastapi
        msg = f"RepeatNode can't have {node.iterations} < 1 iterations."
        raise UnsupportedOperation(msg)

    parent_id = ProgramNode(node.id).id
    pass_node_impl = generate_pass_node_implementation(requested_inputs)

    result = FrontendGraph()
    entry_node = ParsedImplementationNode(
        id=f"leqo_{parent_id.hex}_repeat_entry", implementation=deepcopy(pass_node_impl)
    )
    result.append_node(entry_node)
    prev_id = entry_node.id
    exit_node: ParsedImplementationNode
    for i in range(node.iterations):

        def new_id(old_id: str, i: int = i) -> str:
            return f"leqo_{parent_id.hex}_repeat_{i}_{old_id}"

        exit_node = ParsedImplementationNode(
            id=f"leqo_{parent_id.hex}_repeat_{i}_exit",
            implementation=deepcopy(pass_node_impl),
        )
        result.append_node(exit_node)
        for n in node.block.nodes:
            if n.id == node.id:
                continue
            iter_node = deepcopy(n)
            iter_node.id = new_id(iter_node.id)
            result.append_node(iter_node)
        for e in node.block.edges:
            iter_edge = deepcopy(e)
            source_id = iter_edge.source[0]
            target_id = iter_edge.target[0]
            if source_id == node.id:
                iter_edge.source = (prev_id, iter_edge.source[1])
            else:
                iter_edge.source = (new_id(source_id), iter_edge.source[1])
            if target_id == node.id:
                iter_edge.target = (exit_node.id, iter_edge.target[1])
            else:
                iter_edge.target = (new_id(target_id), iter_edge.target[1])
            result.append_edge(iter_edge)

        prev_id = exit_node.id

    result.rename_nodes({exit_node.id: node.id})
    return (entry_node.id, exit_node.id, result)

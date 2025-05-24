"""
Processing logic for :class:`app.model.CompileRequest.RepeatNode`.
"""

from collections.abc import Callable, Coroutine, Iterator

from app.model.CompileRequest import Edge, NestedBlock, RepeatNode
from app.model.CompileRequest import Node as FrontendNode
from app.processing.converted_graph import ConvertedProgramGraph
from app.processing.graph import ProgramNode, TEdgeData


def _map_node_name(node_name: str, i: int) -> str:
    return f"{node_name}_{i}"


def _get_inner_edges(node_name: str, block: NestedBlock) -> Iterator[Edge]:
    for edge in block.edges:
        if node_name in [edge.source[0], edge.target[0]]:
            continue

        yield edge


def _map_inner_edges(i: int, node_name: str, block: NestedBlock) -> Iterator[Edge]:
    for edge in _get_inner_edges(node_name, block):
        yield edge.model_copy(
            update={
                "source": [_map_node_name(edge.source[0], i), edge.source[1]],
                "target": [_map_node_name(edge.target[0], i), edge.target[1]],
            }
        )


def _map_nodes(i: int, block: NestedBlock) -> Iterator[FrontendNode]:
    for node in block.nodes:
        yield node.model_copy(
            update={
                "id": _map_node_name(node.id, i),
            }
        )


async def flatten_repeat(
    target: ConvertedProgramGraph,
    program_node: ProgramNode,
    frontend_node: RepeatNode,
    enrich_graph: Callable[[ConvertedProgramGraph], Coroutine[None, None, None]],
) -> None:
    inner_graph = ConvertedProgramGraph()

    # Flatten inner nodes
    for i in range(frontend_node.iterations):
        inner_graph.insert(
            nodes=_map_nodes(i, frontend_node.block),
            edges=_map_inner_edges(i, frontend_node.id, frontend_node.block),
        )

        if i == 0:
            continue

        # ToDo: Add edges to predecessor

    # enrich inner graph
    await enrich_graph(inner_graph)

    in_edges: TEdgeData = {}
    out_edges: TEdgeData = {}
    target.get_connections(program_node, in_edges, out_edges)

    # Remove outer repeat node
    target.remove_node(program_node)

    # ToDo: Add incoming connections

    # ToDo: Add outgoing connections

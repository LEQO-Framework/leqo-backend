"""
Provides the core logic of the backend.
"""

from app.model.CompileRequest import CompileRequest
from app.openqasm3.printer import leqo_dumps
from app.processing.enricher import enrich
from app.processing.graph import (
    IOConnection,
    ProgramGraph,
    ProgramNode,
)
from app.processing.merge import merge_nodes
from app.processing.optimize import optimize
from app.processing.post import postprocess
from app.processing.pre import preprocess


def process(body: CompileRequest) -> str:
    lookup: dict[str, ProgramNode] = {}
    graph = ProgramGraph()
    for node in body.nodes:
        enriched_node = enrich(node)

        program_node = ProgramNode(node.id)
        lookup[node.id] = program_node

        processed_node = preprocess(program_node, enriched_node.implementation)
        graph.append_node(processed_node)

    for edge in body.edges:
        graph.append_edge(
            IOConnection(
                (lookup[edge.source[0]], edge.source[1]),
                (lookup[edge.target[0]], edge.target[1]),
            )
        )

    optimize(graph)
    program = merge_nodes(graph)
    program = postprocess(program)
    return leqo_dumps(program)

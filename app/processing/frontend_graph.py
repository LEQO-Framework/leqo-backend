"""Graph structure of the frontend model."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from networkx import DiGraph

from app.enricher import ParsedImplementationNode
from app.model.CompileRequest import Edge
from app.model.CompileRequest import Node as FrontendNode

TBaseNode = FrontendNode | ParsedImplementationNode


if TYPE_CHECKING:
    FrontendGraphBase = DiGraph[str]
else:
    FrontendGraphBase = DiGraph


class FrontendGraph(FrontendGraphBase):
    """Graph representing the frontend model.

    Mainly used to be converted to internal class:`app.processing.graph.ProgramGraph`.
    """

    node_data: dict[str, TBaseNode]
    edge_data: dict[tuple[str, str], list[Edge]]

    def __init__(
        self,
    ) -> None:
        super().__init__()
        self.node_data = {}
        self.edge_data = {}

    def append_node(self, node: TBaseNode) -> None:
        super().add_node(node.id)
        self.node_data[node.id] = node

    def append_edge(self, edge: Edge) -> None:
        super().add_edge(edge.source[0], edge.target[0])
        self.edge_data.setdefault((edge.source[0], edge.target[0]), []).append(edge)

    @staticmethod
    def create(
        nodes: Iterable[TBaseNode],
        edges: Iterable[Edge],
    ) -> FrontendGraph:
        graph = FrontendGraph()
        for node in nodes:
            graph.append_node(node)
        for edge in edges:
            graph.append_edge(edge)
        return graph

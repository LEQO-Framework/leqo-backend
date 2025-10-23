"""
Graph structure of the frontend model.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from networkx import DiGraph, relabel_nodes

from app.enricher import ParsedImplementationNode
from app.model.CompileRequest import Edge
from app.model.CompileRequest import Node as FrontendNode

TBaseNode = FrontendNode | ParsedImplementationNode


if TYPE_CHECKING:
    FrontendGraphBase = DiGraph[str]
else:
    FrontendGraphBase = DiGraph


class FrontendGraph(FrontendGraphBase):
    """
    Graph representing the frontend model.

    Mainly used to be converted to internal class:`app.transformation_manager.graph.ProgramGraph`.
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

    def rename_nodes(self, mapping: dict[str, str]) -> None:
        relabel_nodes(self, mapping, copy=False)
        for old, new in mapping.items():
            old_node = self.node_data.pop(old)
            old_node.id = new
            self.node_data[new] = old_node

            for id_tuple, data in list(self.edge_data.items()):
                if id_tuple[0] == old:
                    for edge in data:
                        edge.source = (new, edge.source[1])
                    self.edge_data.pop(id_tuple)
                    self.edge_data[(new, id_tuple[1])] = data
                if id_tuple[1] == old:
                    for edge in data:
                        edge.target = (new, edge.target[1])
                    self.edge_data.pop(id_tuple)
                    self.edge_data[(id_tuple[0], new)] = data

    @staticmethod
    def create(
        nodes: Iterable[TBaseNode],
        edges: Iterable[Edge],
    ) -> FrontendGraph:
        """
        Build graph from nodes + edges.
        """
        graph = FrontendGraph()
        for node in nodes:
            graph.append_node(node)
        for edge in edges:
            graph.append_edge(edge)
        return graph

"""
Logic to transfer the frontend graph model into the backend graph model.
"""

from collections.abc import Iterable
from typing import TypeVar

from app.enricher import ParsedImplementationNode
from app.model.CompileRequest import Edge
from app.model.CompileRequest import Node as FrontendNode
from app.processing.graph import IOConnection, ProgramGraph, ProgramNode

TBaseNode = TypeVar("TBaseNode", bound=FrontendNode | ParsedImplementationNode)


class ConvertedProgramGraph(ProgramGraph):
    """
    Internal graph model with support for frontend node lookup.
    """

    __lookup: dict[str, tuple[ProgramNode, FrontendNode | ParsedImplementationNode]]

    def __init__(self) -> None:
        super().__init__()

        self.__lookup = {}

    def lookup(
        self, name: str
    ) -> tuple[ProgramNode, FrontendNode | ParsedImplementationNode] | None:
        return self.__lookup.get(name)

    @staticmethod
    def create(
        nodes: Iterable[TBaseNode],
        edges: Iterable[Edge],
    ) -> "ConvertedProgramGraph":
        """
        Transfers the frontend graph model into the backend graph model.

        :param nodes: Frontend nodes to map.
        :param edges: Frontend edges to map.
        :return: The internal graph model.
        """

        graph = ConvertedProgramGraph()
        graph.insert(nodes, edges)
        return graph

    def insert(
        self,
        nodes: Iterable[TBaseNode],
        edges: Iterable[Edge],
    ) -> None:
        """
        Transfers the frontend graph model into an existing backend graph model.
        """

        for frontend_node in nodes:
            program_node = ProgramNode(frontend_node.id)
            self.__lookup[frontend_node.id] = (program_node, frontend_node)
            self.add_node(program_node)

        for edge in edges:
            self.append_edge(
                IOConnection(
                    (self.__lookup[edge.source[0]][0], edge.source[1]),
                    (self.__lookup[edge.target[0]][0], edge.target[1]),
                    edge.identifier,
                    edge.size,
                )
            )

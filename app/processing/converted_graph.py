"""
Logic to transfer the frontend graph model into the backend graph model.
"""

from typing import TypeVar

from app.model.CompileRequest import Edge
from app.model.CompileRequest import Node as FrontendNode
from app.processing.graph import IOConnection, ProgramGraph, ProgramNode
from app.services import NodeIdFactory

TBaseNode = TypeVar("TBaseNode", bound=FrontendNode)


class ConvertedProgramGraph(ProgramGraph):
    """
    Internal graph model with support for frontend node lookup.
    """

    __lookup: dict[str, tuple[ProgramNode, FrontendNode]]

    def __init__(self) -> None:
        super().__init__()
        self.__lookup = {}

    def lookup(self, name: str) -> tuple[ProgramNode, FrontendNode] | None:
        return self.__lookup.get(name)

    @staticmethod
    def create(
        nodes: list[TBaseNode], edges: list[Edge], node_id_factory: NodeIdFactory
    ) -> "ConvertedProgramGraph":
        """
        Transfers the frontend graph model into the backend graph model.

        :param nodes: Frontend nodes to map.
        :param edges: Frontend edges to map.
        :param node_id_factory: Function that creates unique node names.
        :return: The internal graph model.
        """

        graph = ConvertedProgramGraph()

        for frontend_node in nodes:
            program_node = ProgramNode(
                frontend_node.id, id=node_id_factory(frontend_node.id)
            )
            graph.__lookup[frontend_node.id] = (program_node, frontend_node)
            graph.add_node(program_node)

        for edge in edges:
            graph.append_edge(
                IOConnection(
                    (graph.__lookup[edge.source[0]][0], edge.source[1]),
                    (graph.__lookup[edge.target[0]][0], edge.target[1]),
                )
            )

        return graph

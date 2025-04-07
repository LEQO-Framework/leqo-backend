from dataclasses import dataclass
from random import randint, random, shuffle
from typing import TYPE_CHECKING

from networkx import DiGraph, topological_sort


@dataclass(frozen=True)
class Node:
    id: int
    total_required: int = 0
    dirty: int = 0
    reusable: int = 0
    reusable_if_uncompute: int = 0


@dataclass(frozen=True)
class Edge:
    source: Node
    target: Node
    size: int  # 0 for io edge


if TYPE_CHECKING:
    PlayGraph = DiGraph[Node]
else:
    PlayGraph = DiGraph


class Graph(PlayGraph):
    __edges: dict[tuple[Node, Node], Edge]

    def __init__(self) -> None:
        super().__init__()
        self.__edges = {}

    def append_edge(self, edge: Edge) -> None:
        self.__edges[(edge.source, edge.target)] = edge
        super().add_edge(edge.source, edge.target)


def random_node(id: int) -> Node:
    dirty = randint(0, 2)
    total_required = dirty + randint(0, 5)
    reusable = randint(0, 2)
    reusable_if_uncompute = reusable + randint(0, 5)
    return Node(id, total_required, dirty, reusable, reusable_if_uncompute)


def random_graph(size: int) -> Graph:
    nodes: list[Node] = []
    result = Graph()
    for i in range(size):
        new = random_node(i)
        result.add_node(new)
        shuffle(nodes)
        for prev in nodes:
            if prev is new:
                continue
            if random() < 0.5:
                break
            result.append_edge(Edge(prev, new, True))
    return result


def main() -> None:
    g = random_graph(10)
    for node in topological_sort(g):
        print(node)


if __name__ == "__main__":
    main()

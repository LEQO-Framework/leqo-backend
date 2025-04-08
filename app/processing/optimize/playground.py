from dataclasses import dataclass
from io import UnsupportedOperation
from random import randint, random, shuffle
from typing import TYPE_CHECKING, override

from networkx import DiGraph


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
    __edge_data: dict[tuple[Node, Node], Edge]

    def __init__(self) -> None:
        super().__init__()
        self.__edge_data = {}

    def append_edge(self, edge: Edge) -> None:
        self.__edge_data[(edge.source, edge.target)] = edge
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
        nodes.append(new)
        shuffle(nodes)
        for prev in nodes:
            if prev is new:
                continue
            if random() < 0.3:
                break
            result.append_edge(Edge(prev, new, True))
    return result


class Algo:
    graph: Graph
    uncompute: dict[Node, bool]
    added_edges: set[Edge]
    performance: int

    def __init__(self, graph: Graph) -> None:
        self.graph = graph
        self.uncompute = {n: False for n in graph.nodes()}
        self.added_edges = set()
        self.performance = 0
        self.compute()

    def compute(self) -> None:
        raise UnsupportedOperation("not implemented")

    def add_opt_edge(self, edge: Edge) -> None:
        self.performance += edge.size
        self.graph.append_edge(edge)


class NoPredAlgo(Algo):
    def get_no_pred_nodes(self) -> list[Node]:
        return [n for n, pred in self.graph.pred.items() if not pred]

    def remove_node(self, node: Node) -> list[Node]:
        result: list[Node] = []
        succs = list(self.graph.successors(node))
        for succ in succs:
            self.graph.remove_edge(node, succ)
            if not self.graph.pred[succ]:
                result.append(succ)
        return result


class Heuristik1(NoPredAlgo):
    reusable: int
    dirty: int
    order: list[Node]

    def __init__(self, graph: Graph) -> None:
        self.reusable = 0
        self.dirty = 0
        self.order = []
        super().__init__(graph)

    @override
    def compute(self) -> None:
        nopred = self.get_no_pred_nodes()
        while len(nopred) > 0:
            node = nopred.pop()
            self.order.append(node)
            nopred.extend(self.remove_node(node))


def main() -> None:
    g = random_graph(5)
    r = Heuristik1(g)
    print(r.order)


if __name__ == "__main__":
    main()

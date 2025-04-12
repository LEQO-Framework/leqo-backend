from abc import ABC, abstractmethod
from copy import deepcopy
from random import randint, random, shuffle
from typing import override
from uuid import uuid4

from openqasm3.ast import Program

from app.processing.graph import (
    AncillaConnection,
    IOConnection,
    IOInfo,
    ProcessedProgramNode,
    ProgramGraph,
    ProgramNode,
    QubitIOInfo,
    SectionInfo,
)


def random_program(id: int) -> ProcessedProgramNode:
    amount_required_dirty = randint(0, 2)
    amount_required_reusable = randint(0, 8)
    amount_returned_dirty = randint(0, 2)
    amount_returned_reusable = randint(0, 4)
    amount_returned_reusable_after_uncompute = randint(0, 4)

    qubit_id = 0
    required_dirty = [qubit_id + i for i in range(amount_required_dirty)]
    qubit_id += amount_required_dirty
    required_reusable = [qubit_id + i for i in range(amount_required_reusable)]

    qubit_id = 0
    returned_dirty = [qubit_id + i for i in range(amount_returned_dirty)]
    qubit_id += amount_returned_dirty
    returned_reusable = [qubit_id + i for i in range(amount_returned_reusable)]
    qubit_id += amount_returned_reusable
    returned_reusable_after_uncompute = [
        qubit_id + i for i in range(amount_returned_reusable_after_uncompute)
    ]

    return ProcessedProgramNode(
        ProgramNode(str(id), ""),
        Program([]),
        SectionInfo(
            uuid4(),
            IOInfo(
                qubits=QubitIOInfo(
                    required_dirty_ids=required_dirty,
                    required_reusable_ids=required_reusable,
                    returned_dirty_ids=returned_dirty,
                    returned_reusable_ids=returned_reusable,
                    returned_reusable_after_uncompute_ids=returned_reusable_after_uncompute,
                ),
            ),
        ),
        None,
    )


def random_graph(size: int) -> ProgramGraph:
    nodes: list[ProcessedProgramNode] = []
    result = ProgramGraph()
    for i in range(size):
        new = random_program(i)
        result.append_node(new)
        nodes.append(new)
        shuffle(nodes)
        for prev in nodes:
            if prev is new:
                continue
            if random() < 0.3:
                break
            result.append_edge(IOConnection((prev.raw, 0), (new.raw, 0)))
    return result


class AlgoPerf(ABC):
    graph: ProgramGraph
    added_edges: list[AncillaConnection]
    performance: int

    def __init__(self, graph: ProgramGraph) -> None:
        self.graph = graph
        self.added_edges = []
        self.performance = 0

    def add_edge(self, edge: AncillaConnection) -> None:
        self.graph.append_edge(edge)
        self.performance += len(edge.source)

    @abstractmethod
    def compute(self) -> int:
        return self.performance


class DummyAlgo(AlgoPerf):
    @override
    def compute(self) -> int:
        return super().compute()


class NoPredWithSimpleHeuristik(AlgoPerf):
    @override
    def compute(self) -> int:
        return super().compute()


def main() -> None:
    contenders: dict[type[AlgoPerf], int] = {
        DummyAlgo: 0,
        NoPredWithSimpleHeuristik: 0,
    }
    for _ in range(100):
        graph = random_graph(50)
        for algo in contenders:
            instance = algo(deepcopy(graph))
            contenders[algo] += instance.compute()

    for algo, perf in sorted(contenders.items(), key=lambda x: x[1], reverse=True):
        print(f"{algo.__name__} -> {perf}")


if __name__ == "__main__":
    main()

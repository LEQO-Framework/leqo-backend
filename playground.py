from abc import ABC, abstractmethod
from copy import deepcopy
from random import randint, random, shuffle
from textwrap import dedent
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
    amount_required_reusable = randint(0, 8)
    amount_required_dirty = randint(0, 2)
    amount_returned_reusable = randint(0, 2)
    amount_returned_reusable_after_uncompute = randint(0, 4)
    amount_returned_dirty = randint(0, 2)

    qubit_id = 0
    required_reusable = [qubit_id + i for i in range(amount_required_reusable)]
    qubit_id += amount_required_reusable
    required_dirty = [qubit_id + i for i in range(amount_required_dirty)]

    qubit_id = 0
    returned_reusable = [qubit_id + i for i in range(amount_returned_reusable)]
    qubit_id += amount_returned_reusable
    returned_reusable_after_uncompute = [
        qubit_id + i for i in range(amount_returned_reusable_after_uncompute)
    ]
    qubit_id += amount_returned_reusable_after_uncompute
    returned_dirty = [qubit_id + i for i in range(amount_returned_dirty)]

    return ProcessedProgramNode(
        ProgramNode(str(id), ""),
        Program([]),
        SectionInfo(
            uuid4(),
            IOInfo(
                qubits=QubitIOInfo(
                    required_reusable_ids=required_reusable,
                    required_dirty_ids=required_dirty,
                    returned_reusable_after_uncompute_ids=returned_reusable_after_uncompute,
                    returned_reusable_ids=returned_reusable,
                    returned_dirty_ids=returned_dirty,
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


def print_ancilla_edges(edges: list[AncillaConnection]) -> None:
    print("\n=== Ancilla Edges ===")
    for edge in edges:
        print(
            dedent(f"""
                   == {edge.source[0].name} -> {edge.target[0].name} ==
                   {edge.source[1]} -> {edge.target[1]}
                   """).strip(),
        )


def print_graph(graph: ProgramGraph) -> None:
    print("=== Nodes ===")
    for nd in graph.nodes():
        node = graph.get_data_node(nd)
        name = node.raw.name
        io = node.info.io.qubits
        print(
            dedent(f"""
                   == Node {name} ==
                   = Input =
                   Clean: {len(io.required_reusable_ids)} {io.required_reusable_ids}
                   Dirty: {len(io.required_dirty_ids)} {io.required_dirty_ids}
                   == Output ==
                   Clean:  {len(io.returned_reusable_ids)} {io.returned_reusable_ids}
                   Uncom:  {len(io.returned_reusable_after_uncompute_ids)} {io.returned_reusable_after_uncompute_ids}
                   Dirty:  {len(io.returned_dirty_ids)} {io.returned_dirty_ids}
                   """).strip(),
        )
    io_edges: list[IOConnection] = []
    ancilla_edges: list[AncillaConnection] = []
    for edge in graph.edges():
        data = graph.get_data_edges(*edge)
        for subedge in data:
            match subedge:
                case IOConnection():
                    io_edges.append(subedge)
                case AncillaConnection():
                    ancilla_edges.append(subedge)

    print("\n=== IO Edges ===")
    for subedge in io_edges:
        print(f"""== {subedge.source[0].name} -> {subedge.target[0].name} ==""")
    print_ancilla_edges(ancilla_edges)


class AlgoPerf(ABC):
    graph: ProgramGraph
    added_edges: list[AncillaConnection]
    uncomputed: dict[ProgramNode, bool]

    def __init__(self, graph: ProgramGraph) -> None:
        self.graph = graph
        self.added_edges = []
        self.uncomputed = {n: False for n in self.graph.nodes()}

    def add_edge(self, edge: AncillaConnection) -> None:
        self.graph.append_edge(edge)
        self.added_edges.append(edge)

    def uncompute_node(self, node: ProcessedProgramNode) -> None:
        self.uncomputed[node.raw] = True

    @abstractmethod
    def compute(self) -> tuple[int, int]:
        return sum([len(ac.source[1]) for ac in self.added_edges]), len(
            [k for k, v in self.uncomputed.items() if v],
        )


class DummyAlgo(AlgoPerf):
    @override
    def compute(self) -> tuple[int, int]:
        return super().compute()


class NoPredDummy(AlgoPerf):
    reusable: list[ProcessedProgramNode]
    dirty: list[ProcessedProgramNode]
    uncomputable: list[ProcessedProgramNode]
    nopred: list[ProcessedProgramNode]

    def __init__(self, graph: ProgramGraph) -> None:
        super().__init__(graph)
        self.reusable = []
        self.dirty = []
        self.uncomputable = []
        self.nopred = [
            self.graph.get_data_node(n)
            for n, pred in self.graph.pred.items()
            if not pred
        ]

    def remove_node(self, node: ProcessedProgramNode) -> list[ProcessedProgramNode]:
        result: list[ProcessedProgramNode] = []
        succs = list(self.graph.successors(node.raw))
        for succ in succs:
            self.graph.remove_edge(node.raw, succ)
            if not self.graph.pred[succ]:
                result.append(self.graph.get_data_node(succ))
        return result

    def get_and_remove_next_nopred(self) -> ProcessedProgramNode:
        return self.nopred.pop()

    def get_and_remove_next_uncompute(self) -> ProcessedProgramNode:
        return self.uncomputable.pop()

    @override
    def compute(self) -> tuple[int, int]:
        while len(self.nopred) > 0:
            node = self.get_and_remove_next_nopred()
            self.nopred.extend(self.remove_node(node))

            need_dirty = node.info.io.qubits.required_dirty_ids
            while len(need_dirty) > 0 and len(self.dirty) > 0:
                source = self.dirty[0]
                possible_source_ids = source.info.io.qubits.returned_dirty_ids
                size = min(len(need_dirty), len(possible_source_ids))
                target_ids = need_dirty[:size]
                need_dirty = need_dirty[size:]
                source_ids = possible_source_ids[:size]
                source.info.io.qubits.returned_dirty_ids = possible_source_ids[size:]
                self.add_edge(
                    AncillaConnection(
                        (source.raw, source_ids),
                        (node.raw, target_ids),
                    ),
                )
                if len(source.info.io.qubits.returned_dirty_ids) == 0:
                    self.dirty.remove(source)
            while len(need_dirty) > 0 and len(self.uncomputable) > 0:
                source = self.uncomputable[0]
                possible_source_ids = (
                    source.info.io.qubits.returned_reusable_after_uncompute_ids
                )
                size = min(len(need_dirty), len(possible_source_ids))
                target_ids = need_dirty[:size]
                need_dirty = need_dirty[size:]
                source_ids = possible_source_ids[:size]
                source.info.io.qubits.returned_reusable_after_uncompute_ids = (
                    possible_source_ids[size:]
                )
                self.add_edge(
                    AncillaConnection(
                        (source.raw, source_ids),
                        (node.raw, target_ids),
                    ),
                )
                if (
                    len(source.info.io.qubits.returned_reusable_after_uncompute_ids)
                    == 0
                ):
                    self.uncomputable.remove(source)

            need_reusable = node.info.io.qubits.required_reusable_ids
            while len(need_reusable) > 0 and (
                len(self.uncomputable) > 0 or len(self.reusable) > 0
            ):
                while len(need_reusable) > 0 and len(self.reusable) > 0:
                    source = self.reusable[0]
                    possible_source_ids = source.info.io.qubits.returned_reusable_ids
                    size = min(len(need_reusable), len(possible_source_ids))
                    target_ids = need_reusable[:size]
                    need_reusable = need_reusable[size:]
                    source_ids = possible_source_ids[:size]
                    source.info.io.qubits.returned_reusable_ids = possible_source_ids[
                        size:
                    ]
                    self.add_edge(
                        AncillaConnection(
                            (source.raw, source_ids),
                            (node.raw, target_ids),
                        ),
                    )
                    if len(source.info.io.qubits.returned_reusable_ids) == 0:
                        self.reusable.remove(source)

                if (
                    len(need_reusable) > 0 and len(self.uncomputable) > 0
                ):  # means that len(self.reusable) is empty
                    new_reusable = self.get_and_remove_next_uncompute()
                    self.reusable.append(new_reusable)
                    new_reusable.info.io.qubits.returned_reusable_ids = new_reusable.info.io.qubits.returned_reusable_after_uncompute_ids
                    self.uncompute_node(new_reusable)

            returned_dirty = node.info.io.qubits.returned_dirty_ids
            returned_reusable = node.info.io.qubits.returned_reusable_ids
            returned_uncomputable = (
                node.info.io.qubits.returned_reusable_after_uncompute_ids
            )
            if len(returned_dirty) > 0:
                self.dirty.append(node)
            if len(returned_reusable) > 0:
                self.reusable.append(node)
            if len(returned_uncomputable) > 0:
                self.uncomputable.append(node)

        return super().compute()


class NoPredReturnedReusable(NoPredDummy):
    @override
    def get_and_remove_next_nopred(self) -> ProcessedProgramNode:
        self.nopred.sort(
            key=lambda x: len(x.info.io.qubits.returned_reusable_ids)
            + len(x.info.io.qubits.returned_reusable_after_uncompute_ids),
            reverse=True,
        )
        result, self.nopred = self.nopred[0], self.nopred[1:]
        return result


class NoPredRequiredReusable(NoPredDummy):
    @override
    def get_and_remove_next_nopred(self) -> ProcessedProgramNode:
        self.nopred.sort(
            key=lambda x: len(x.info.io.qubits.required_reusable_ids),
            reverse=False,
        )
        result, self.nopred = self.nopred[0], self.nopred[1:]
        return result


class NoPredReturnedRequiredDifference(NoPredDummy):
    @override
    def get_and_remove_next_nopred(self) -> ProcessedProgramNode:
        self.nopred.sort(
            key=lambda x: len(x.info.io.qubits.returned_reusable_ids)
            - len(x.info.io.qubits.required_reusable_ids),
            reverse=True,
        )
        result, self.nopred = self.nopred[0], self.nopred[1:]
        return result


class NoPredReturnedRequiredQuotient(NoPredDummy):
    @override
    def get_and_remove_next_nopred(self) -> ProcessedProgramNode:
        self.nopred.sort(
            key=lambda x: (
                len(x.info.io.qubits.returned_reusable_ids)
                + len(x.info.io.qubits.returned_reusable_after_uncompute_ids)
                + 1
            )
            / (len(x.info.io.qubits.required_reusable_ids) + 1),
            reverse=True,
        )
        result, self.nopred = self.nopred[0], self.nopred[1:]
        return result


class NoSuccDummy(AlgoPerf):
    reusable: list[ProcessedProgramNode]
    dirty: list[ProcessedProgramNode]
    nosucc: list[ProcessedProgramNode]

    def __init__(self, graph: ProgramGraph) -> None:
        super().__init__(graph)
        self.reusable = []
        self.dirty = []
        self.nosucc = [
            self.graph.get_data_node(n)
            for n, succ in self.graph.succ.items()
            if not succ
        ]

    def remove_node(self, node: ProcessedProgramNode) -> list[ProcessedProgramNode]:
        result: list[ProcessedProgramNode] = []
        preds = list(self.graph.predecessors(node.raw))
        for pred in preds:
            self.graph.remove_edge(pred, node.raw)
            if not self.graph.succ[pred]:
                result.append(self.graph.get_data_node(pred))
        return result

    def get_and_remove_next_nosucc(self) -> ProcessedProgramNode:
        return self.nosucc.pop()

    @override
    def compute(self) -> tuple[int, int]:
        while len(self.nosucc) > 0:
            node = self.get_and_remove_next_nosucc()
            self.nosucc.extend(self.remove_node(node))

            got_dirty = node.info.io.qubits.returned_dirty_ids
            while len(got_dirty) > 0 and len(self.dirty) > 0:
                target = self.dirty[0]
                possible_target_ids = target.info.io.qubits.required_dirty_ids
                size = min(len(got_dirty), len(possible_target_ids))
                source_ids = got_dirty[:size]
                got_dirty = got_dirty[size:]
                target_ids = possible_target_ids[:size]
                target.info.io.qubits.required_dirty_ids = possible_target_ids[size:]
                self.add_edge(
                    AncillaConnection(
                        (node.raw, source_ids),
                        (target.raw, target_ids),
                    ),
                )
                if len(target.info.io.qubits.required_dirty_ids) == 0:
                    self.dirty.remove(target)

            got_uncomputable = node.info.io.qubits.returned_reusable_after_uncompute_ids
            while len(got_uncomputable) > 0 and len(self.dirty) > 0:
                target = self.dirty[0]
                possible_target_ids = target.info.io.qubits.required_dirty_ids
                size = min(len(got_uncomputable), len(possible_target_ids))
                source_ids = got_uncomputable[:size]
                got_uncomputable = got_uncomputable[size:]
                target_ids = possible_target_ids[:size]
                target.info.io.qubits.required_dirty_ids = possible_target_ids[size:]
                self.add_edge(
                    AncillaConnection(
                        (node.raw, source_ids),
                        (target.raw, target_ids),
                    ),
                )
                if len(target.info.io.qubits.required_dirty_ids) == 0:
                    self.dirty.remove(target)

            got_reusable = node.info.io.qubits.returned_reusable_ids
            while len(self.reusable) > 0 and (
                len(got_reusable) > 0 or len(got_uncomputable)
            ):
                while len(got_reusable) > 0 and len(self.reusable) > 0:
                    target = self.reusable[0]
                    possible_target_ids = target.info.io.qubits.required_reusable_ids
                    size = min(len(got_reusable), len(possible_target_ids))
                    source_ids = got_reusable[:size]
                    got_reusable = got_reusable[size:]
                    target_ids = possible_target_ids[:size]
                    target.info.io.qubits.required_reusable_ids = possible_target_ids[
                        size:
                    ]
                    self.add_edge(
                        AncillaConnection(
                            (node.raw, source_ids),
                            (target.raw, target_ids),
                        ),
                    )
                    if len(target.info.io.qubits.required_reusable_ids) == 0:
                        self.reusable.remove(target)

                if len(got_uncomputable) > 0 and len(self.reusable) > 0:
                    self.uncompute_node(node)
                    got_reusable = got_uncomputable
                    got_uncomputable = []

            required_dirty = node.info.io.qubits.required_dirty_ids
            required_reusable = node.info.io.qubits.required_reusable_ids
            if len(required_dirty) > 0:
                self.dirty.append(node)
            if len(required_reusable) > 0:
                self.reusable.append(node)

        return super().compute()


class NoSuccRequiredReusable(NoSuccDummy):
    @override
    def get_and_remove_next_nosucc(self) -> ProcessedProgramNode:
        self.nosucc.sort(
            key=lambda x: len(x.info.io.qubits.required_reusable_ids),
            reverse=True,
        )
        result, self.nosucc = self.nosucc[0], self.nosucc[1:]
        return result


class NoSuccReturnedRequiredDifference(NoSuccDummy):
    @override
    def get_and_remove_next_nosucc(self) -> ProcessedProgramNode:
        self.nosucc.sort(
            key=lambda x: len(x.info.io.qubits.returned_reusable_ids)
            - len(x.info.io.qubits.required_reusable_ids),
            reverse=False,
        )
        result, self.nosucc = self.nosucc[0], self.nosucc[1:]
        return result


class NoSuccReturnedRequiredQuotient(NoSuccDummy):
    @override
    def get_and_remove_next_nosucc(self) -> ProcessedProgramNode:
        self.nosucc.sort(
            key=lambda x: (
                len(x.info.io.qubits.returned_reusable_ids)
                + len(x.info.io.qubits.returned_reusable_after_uncompute_ids)
                + 1
            )
            / (len(x.info.io.qubits.required_reusable_ids) + 1),
            reverse=False,
        )
        result, self.nosucc = self.nosucc[0], self.nosucc[1:]
        return result


def main() -> None:
    contenders: dict[type[AlgoPerf], tuple[int, int]] = {
        DummyAlgo: (0, 0),
        NoPredDummy: (0, 0),
        NoPredReturnedReusable: (0, 0),
        NoPredRequiredReusable: (0, 0),
        NoPredReturnedRequiredDifference: (0, 0),
        NoPredReturnedRequiredQuotient: (0, 0),
        NoSuccDummy: (0, 0),
        NoSuccRequiredReusable: (0, 0),
        NoSuccReturnedRequiredDifference: (0, 0),
        NoSuccReturnedRequiredQuotient: (0, 0),
    }
    for _ in range(50):
        graph = random_graph(100)
        for algo, cur in contenders.items():
            instance = algo(deepcopy(graph))
            perf, uncomputed = instance.compute()
            contenders[algo] = cur[0] + perf, cur[1] + uncomputed
        # nopred = NoPredRequiredReusable(deepcopy(graph))
        # nosucc = NoSuccRequiredReusable(deepcopy(graph))
        # pc, pu = nopred.compute()
        # sc, su = nosucc.compute()
        # if pc > sc:
        #     breakpoint()

    for algo, perf_uncomp in sorted(
        contenders.items(),
        key=lambda x: x[1][0],
        reverse=True,
    ):
        print(f"{algo.__name__} -> {perf_uncomp}")


if __name__ == "__main__":
    main()

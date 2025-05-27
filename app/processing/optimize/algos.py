"""Optimization algorithms.

Following task has to be solved:

Given:

- set of nodes, each node has:
    - amount of required reusable ancilla qubits
    - amount of required dirty ancilla qubits
    - amount of returned reusable ancilla qubits
    - amount of returned dirty ancilla qubits
    - amount of returned 'reusable if uncomputed, else dirty' qubits
- set of connections between these nodes

Wanted:

- set of ancilla edges that reuse dirty/reusable ancillas
    - topological sort has to be possible after!
- dict that tells whether to uncompute a given node
- optimize on minimal amount of required qubits (that could not be satisfied via ancilla connections)

Note on ancilla qubit types:

- returned reusable qubits can be used as required dirty and required reusable
- returned dirty qubits can be used as required dirty
- returned uncomputable can be used as:
    - required dirty in any case
    - required dirty and required reusable if uncompute is executed
"""

from abc import ABC, abstractmethod
from sys import maxsize
from typing import override

from app.processing.graph import (
    AncillaConnection,
    ProcessedProgramNode,
    ProgramGraph,
    ProgramNode,
)


class OptimizationAlgo(ABC):
    """Abstract parent of optimization algorithms.

    - Specify the interface.
    - Handle special user-required ancilla nodes.
    """

    graph: ProgramGraph

    def __init__(self, graph: ProgramGraph) -> None:
        for raw in graph.nodes:
            if raw.is_ancilla_node:
                graph.get_data_node(raw).qubit.required_reusable_ids.clear()
        self.graph = graph

    @abstractmethod
    def compute(self) -> tuple[list[AncillaConnection], dict[ProgramNode, bool]]:
        pass


class NoPred(OptimizationAlgo):
    """Implementation of the 'no predecessor' idea with dummy selection.

    Other Algorithms should inherit from this and only override the heuristic methods.

    Basic idea:

    1. Create a set of all nodes that have no predecessor
    2. Keep track of the resources the already fixed nodes have: dirty, uncomputable, reusable
        - all initialized to zero
    3. While the set is not empty:
        1. Choose one node from this set.
            - how to choose is the hard part that has to be done via heuristic
        2. Remove all edges from this node.
        3. Check for new nodes without predecessors, add them to the set.
        4. Try to satisfy the requirements of the current node via the available resources.
            - Add ancilla edges here
            - Possibility to uncompute in previous nodes
            - Needs heuristic: What nodes to uncompute first?
        5. Add the resources this node gives to the available resources.
    4. (Optional): Raise error if there are nodes that were not processed.
        - This would mean that the graph has no topological sort.

    :param ancilla_edges: ancilla edges to return
    :param uncomputes: whether to uncompute a node
    :param reusable: list of nodes that have reusable qubits.
    :param dirty: list of nodes that have dirty qubits.
    :param uncomputable: list of nodes that have uncomputable qubits.
    :param nopred: list of nodes without predecessors (ProcessedProgramNode is not hashable).
    :param need_dirty: current requirement of dirty qubits
    :param need_reusable: current requirement of reusable qubits
    """

    ancilla_edges: list[AncillaConnection]
    uncomputes: dict[ProgramNode, bool]
    reusable: list[ProcessedProgramNode]
    dirty: list[ProcessedProgramNode]
    uncomputable: list[ProcessedProgramNode]
    nopred: list[ProcessedProgramNode]
    need_dirty: list[int]
    need_reusable: list[int]

    @override
    def __init__(self, graph: ProgramGraph) -> None:
        super().__init__(graph)
        self.ancilla_edges = []
        self.uncomputes = dict.fromkeys(graph.nodes, False)
        self.reusable = []
        self.dirty = []
        self.uncomputable = []
        self.nopred = [
            self.graph.get_data_node(n)
            for n, pred in self.graph.pred.items()
            if not pred
        ]
        self.need_dirty = []
        self.need_reusable = []

    def remove_node(self, node: ProcessedProgramNode) -> list[ProcessedProgramNode]:
        """(Virtually) remove node from graph.

        Don't remove the node itself, but all connections outgoing from him.
        It is not possible that the node is incoming edges (invariant of this algo).

        :param node: The node to remove.
        :return: Nodes that have no predecessor because of this.
        """
        result: list[ProcessedProgramNode] = []
        succs = list(self.graph.successors(node.raw))
        for succ in succs:
            self.graph.remove_edge(node.raw, succ)
            if not self.graph.pred[succ]:
                result.append(self.graph.get_data_node(succ))
        return result

    def pop_nopred(self) -> ProcessedProgramNode:
        """Remove and return the next nopred node.

        This is a dummy implementation!
        Overwrite this method is sub-classes.

        :return: Chosen node.
        """
        return self.nopred.pop()

    def pop_uncomputable(self) -> ProcessedProgramNode:
        """Remove and return the next node to be uncomputed.

        Chooses the node with the fewest uncomputable qubits, i.e. the cheapest to uncompute.

        :return: Chosen node.
        """
        if len(self.uncomputable) == 0:
            msg = "No uncomputable nodes available to pop."
            raise RuntimeError(msg)

        result = min(
            self.uncomputable,
            key=lambda n: len(n.qubit.returned_uncomputable_ids),
        )

        self.uncomputable.remove(result)
        return result

    def satisfy_dirty_qubit_requirement(self) -> None:
        """Try to satisfy requirement for dirty qubits.

        Add ancilla edges from previous nodes for this case.
        Use the qubits in the order: dirty -> uncomputable -> reusable
        """
        if self.current_node is None:
            raise RuntimeError

        need_dirty = self.current_node.qubit.required_dirty_ids

        while len(need_dirty) > 0 and len(self.dirty) > 0:
            source = self.dirty[0]
            possible_source_ids = source.qubit.returned_dirty_ids
            size = min(len(need_dirty), len(possible_source_ids))
            target_ids = need_dirty[:size]
            need_dirty = need_dirty[size:]
            source_ids = possible_source_ids[:size]
            source.qubit.returned_dirty_ids = possible_source_ids[size:]
            self.ancilla_edges.append(
                AncillaConnection(
                    (source.raw, source_ids),
                    (self.current_node.raw, target_ids),
                ),
            )
            if len(source.qubit.returned_dirty_ids) == 0:
                self.dirty.remove(source)

        while len(need_dirty) > 0 and len(self.uncomputable) > 0:
            source = self.uncomputable[0]
            possible_source_ids = source.qubit.returned_uncomputable_ids
            size = min(len(need_dirty), len(possible_source_ids))
            target_ids = need_dirty[:size]
            need_dirty = need_dirty[size:]
            source_ids = possible_source_ids[:size]
            source.qubit.returned_uncomputable_ids = possible_source_ids[size:]
            self.ancilla_edges.append(
                AncillaConnection(
                    (source.raw, source_ids),
                    (self.current_node.raw, target_ids),
                ),
            )
            if len(source.qubit.returned_uncomputable_ids) == 0:
                self.uncomputable.remove(source)

        while len(need_dirty) > 0 and len(self.reusable) > 0:
            source = self.reusable[0]
            possible_source_ids = source.qubit.returned_reusable_ids
            size = min(len(need_dirty), len(possible_source_ids))
            target_ids = need_dirty[:size]
            need_dirty = need_dirty[size:]
            source_ids = possible_source_ids[:size]
            source.qubit.returned_reusable_ids = possible_source_ids[size:]
            self.ancilla_edges.append(
                AncillaConnection(
                    (source.raw, source_ids),
                    (self.current_node.raw, target_ids),
                ),
            )
            if len(source.qubit.returned_reusable_ids) == 0:
                self.reusable.remove(source)

    def satisfy_reusable_qubit_requirement(self) -> None:
        """Try to satisfy requirement for dirty qubits.

        Add ancilla edges from previous nodes for this case.
        Try to satisfy with reusable qubits, uncompute nodes if that is not enough.
        """
        if self.current_node is None:
            raise RuntimeError

        need_reusable = self.current_node.qubit.required_reusable_ids

        while len(need_reusable) > 0 and (
            len(self.uncomputable) > 0 or len(self.reusable) > 0
        ):
            while len(need_reusable) > 0 and len(self.reusable) > 0:
                source = self.reusable[0]
                possible_source_ids = source.qubit.returned_reusable_ids
                size = min(len(need_reusable), len(possible_source_ids))
                target_ids = need_reusable[:size]
                need_reusable = need_reusable[size:]
                source_ids = possible_source_ids[:size]
                source.qubit.returned_reusable_ids = possible_source_ids[size:]
                self.ancilla_edges.append(
                    AncillaConnection(
                        (source.raw, source_ids),
                        (self.current_node.raw, target_ids),
                    ),
                )
                if len(source.qubit.returned_reusable_ids) == 0:
                    self.reusable.remove(source)

            if len(need_reusable) > 0 and len(self.uncomputable) > 0:
                new_reusable = self.pop_uncomputable()
                self.reusable.append(new_reusable)
                new_reusable.qubit.returned_reusable_ids.extend(
                    new_reusable.qubit.returned_uncomputable_ids,
                )
                new_reusable.qubit.returned_uncomputable_ids.clear()
                self.uncomputes[new_reusable.raw] = True

    @override
    def compute(self) -> tuple[list[AncillaConnection], dict[ProgramNode, bool]]:
        """Execute the optimization.

        :return: Added ancilla edges and dict specifying whether to uncomute nodes.
        """
        while len(self.nopred) > 0:
            self.current_node = self.pop_nopred()
            self.nopred.extend(self.remove_node(self.current_node))

            self.satisfy_dirty_qubit_requirement()
            self.satisfy_reusable_qubit_requirement()

            if len(self.current_node.qubit.returned_dirty_ids) > 0:
                self.dirty.append(self.current_node)
            if len(self.current_node.qubit.returned_reusable_ids) > 0:
                self.reusable.append(self.current_node)
            if len(self.current_node.qubit.returned_uncomputable_ids) > 0:
                self.uncomputable.append(self.current_node)

        return self.ancilla_edges, self.uncomputes


class NoPredCheckNeedDiffScore(NoPred):
    """NoPred variant with the check-need strategy + diff score.

    Check need strategy:
    All possible nodes are divided in one of two categories:

    1. satisfied: the requirement of that node are satisfied by the available resources
    2. unsatisfied: the requirement of that node can't be satisfied

    We always prefer nodes that are in the first category.

    Diff score:
    Sort the nodes based on provided resources - required resources.

    :param weight_reusable: weight of reusable qubits in diff-score
    :param weight_uncomp: weight of uncomputable qubits in diff-score
    :param weight_dirty: weight of dirty qubits in diff-score
    """

    weight_reusable: int = 2
    weight_uncomp: int = 2
    weight_dirty: int = 1

    @override
    def pop_nopred(self) -> ProcessedProgramNode:
        total_reusable = sum(
            [len(n.qubit.returned_reusable_ids) for n in self.reusable],
        )
        total_dirty = sum(
            [len(n.qubit.required_dirty_ids) for n in self.dirty],
        )
        total_uncomputable = sum(
            [len(n.qubit.returned_uncomputable_ids) for n in self.uncomputable],
        )
        current_best: tuple[bool, int, None | ProcessedProgramNode] = (
            False,
            -maxsize - 1,
            None,
        )
        for node in self.nopred:
            required_dirty = len(node.qubit.required_dirty_ids)
            required_reusable = len(node.qubit.required_reusable_ids)
            satisfied = (
                required_dirty < total_dirty + total_uncomputable
                and required_reusable < total_reusable + total_uncomputable
                and required_dirty + required_reusable
                < total_dirty + total_reusable + total_uncomputable
            )
            if not satisfied and current_best[0]:
                continue
            score = (
                len(node.qubit.returned_reusable_ids) * self.weight_reusable
                + len(node.qubit.returned_uncomputable_ids) * self.weight_uncomp
                + len(node.qubit.returned_dirty_ids) * self.weight_dirty
                - required_reusable * self.weight_reusable
                - required_dirty * self.weight_dirty
            )
            if score < current_best[1]:
                continue
            current_best = (satisfied, score, node)

        choice = current_best[2]
        if choice is None:
            msg = "No nopred node available to pop."
            raise RuntimeError(msg)

        self.nopred.remove(choice)
        return choice

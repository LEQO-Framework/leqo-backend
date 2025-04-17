"""Algorithms based on the 'no predecessor' (NoPred) idea.

Basic idea:
1. Create a set of all nodes that have no predecessor,
    they could be the start of our topological sort.
2. Keep track of the resources the already fixed nodes have: dirty, uncomputable, reusable
    - currently there is nothing of any resource
3. While the set is not empty:
    1. Choose one node from this set.
        - how to choose is the hard part that has to be done via heuristic.
    2. Remove all edges from this node.
    3. Check for new nodes without predecessors, add them to the set.
    4. Try to satisfy the requirements of the current node via the available resources.
        - Add ancilla edges here
        - Possibility to uncompute in previous nodes
        - Need heuristic: What nodes to uncompute first?
    5. Add the resources this node gives to the available resources.
4. (Optional): Raise error if there are nodes that where not processed.
    - This would mean that the graph has no topological sort.
"""

from typing import override

from app.processing.graph import (
    AncillaConnection,
    ProcessedProgramNode,
    ProgramGraph,
    ProgramNode,
)
from app.processing.optimize import OptimizationAlgo


class NoPred(OptimizationAlgo):
    """Implementation of the no predecessor idea with dummy selection.

    Other Algorithms should inherit from this and only override the heuristic methods.

    :param ancilla_edges: ancilla edges to return
    :param uncomputes: whether to uncompute a node
    :param reusable: list of nodes that have reusable qubits.
    :param dirty: list of nodes that have reusable qubits.
    :param uncomputable: list of nodes that have reusable qubits.
    :param nopred: list of nodes without predecessors (ProcessedProgramNode is not hashable).
    :param need_dirty: current requirement of dirty qubits
    :param need_reusable: current requirement of dirty qubits
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
        self.uncomputes = {n: False for n in graph.nodes}
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

        :return: Chosen node.
        """
        return self.nopred.pop()

    def pop_uncomputable(self) -> ProcessedProgramNode:
        """Remove and return the next node to be uncomputed.

        Chooses the node with the fewest uncomputable qubits, i.e., the cheapest to uncompute.

        :return: Chosen node.
        """
        if len(self.uncomputable) == 0:
            msg = "No uncomputable nodes available to pop."
            raise RuntimeError(msg)

        result = min(
            self.uncomputable,
            key=lambda n: len(
                n.info.io.qubits.returned_reusable_after_uncompute_ids,
            ),
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

        need_dirty = self.current_node.info.io.qubits.required_dirty_ids

        while len(need_dirty) > 0 and len(self.dirty) > 0:
            source = self.dirty[0]
            possible_source_ids = source.info.io.qubits.returned_dirty_ids
            size = min(len(need_dirty), len(possible_source_ids))
            target_ids = need_dirty[:size]
            need_dirty = need_dirty[size:]
            source_ids = possible_source_ids[:size]
            source.info.io.qubits.returned_dirty_ids = possible_source_ids[size:]
            self.ancilla_edges.append(
                AncillaConnection(
                    (source.raw, source_ids),
                    (self.current_node.raw, target_ids),
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
            self.ancilla_edges.append(
                AncillaConnection(
                    (source.raw, source_ids),
                    (self.current_node.raw, target_ids),
                ),
            )
            if len(source.info.io.qubits.returned_reusable_after_uncompute_ids) == 0:
                self.uncomputable.remove(source)

        while len(need_dirty) > 0 and len(self.reusable) > 0:
            source = self.reusable[0]
            possible_source_ids = source.info.io.qubits.returned_reusable_ids
            size = min(len(need_dirty), len(possible_source_ids))
            target_ids = need_dirty[:size]
            need_dirty = need_dirty[size:]
            source_ids = possible_source_ids[:size]
            source.info.io.qubits.returned_reusable_ids = possible_source_ids[size:]
            self.ancilla_edges.append(
                AncillaConnection(
                    (source.raw, source_ids),
                    (self.current_node.raw, target_ids),
                ),
            )
            if len(source.info.io.qubits.returned_reusable_ids) == 0:
                self.reusable.remove(source)

    def satisfy_reusable_qubit_requirement(self) -> None:
        """Try to satisfy requirement for dirty qubits.

        Add ancilla edges from previous nodes for this case.
        Try to satisfy with reusable qubits, uncompute nodes if that is not enough.
        """
        if self.current_node is None:
            raise RuntimeError

        need_reusable = self.current_node.info.io.qubits.required_reusable_ids

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
                source.info.io.qubits.returned_reusable_ids = possible_source_ids[size:]
                self.ancilla_edges.append(
                    AncillaConnection(
                        (source.raw, source_ids),
                        (self.current_node.raw, target_ids),
                    ),
                )
                if len(source.info.io.qubits.returned_reusable_ids) == 0:
                    self.reusable.remove(source)

            if len(need_reusable) > 0 and len(self.uncomputable) > 0:
                new_reusable = self.pop_uncomputable()
                self.reusable.append(new_reusable)
                new_reusable.info.io.qubits.returned_reusable_ids.extend(
                    new_reusable.info.io.qubits.returned_reusable_after_uncompute_ids,
                )
                new_reusable.info.io.qubits.returned_reusable_after_uncompute_ids = []
                self.uncomputes[new_reusable.raw] = True

    @override
    def compute(self) -> tuple[list[AncillaConnection], dict[ProgramNode, bool]]:
        """Compute ancillas and uncomputes based on no-pred."""
        while len(self.nopred) > 0:
            self.current_node = self.pop_nopred()
            self.nopred.extend(self.remove_node(self.current_node))

            self.satisfy_dirty_qubit_requirement()
            self.satisfy_reusable_qubit_requirement()

            if len(self.current_node.info.io.qubits.returned_dirty_ids) > 0:
                self.dirty.append(self.current_node)
            if len(self.current_node.info.io.qubits.returned_reusable_ids) > 0:
                self.reusable.append(self.current_node)
            if (
                len(
                    self.current_node.info.io.qubits.returned_reusable_after_uncompute_ids,
                )
                > 0
            ):
                self.uncomputable.append(self.current_node)

        return self.ancilla_edges, self.uncomputes


class NoPredCheckNeed(NoPred):
    pass
    # TODO: port this from playground

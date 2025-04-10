from dataclasses import dataclass
from io import UnsupportedOperation
from uuid import UUID

from openqasm3.ast import (
    AliasStatement,
    DiscreteSet,
    Identifier,
    IndexExpression,
    IntegerLiteral,
    QASMNode,
    QubitDeclaration,
)

from app.openqasm3.visitor import LeqoTransformer
from app.processing.graph import (
    AncillaConnection,
    IOConnection,
    IOInfo,
    ProgramGraph,
)


@dataclass(frozen=True)
class SingleQubit:
    """Give an qubit a unique ID in the whole program.

    Combines section_id and qubit id (of that single section).
    """

    section_id: UUID
    id_in_section: int


class QubitDeclarationToAlias(LeqoTransformer[None]):
    """Replace all qubit declarations with alias to global qubit-reg."""

    section_id: UUID
    qubit_to_index: dict[SingleQubit, int]
    io_info: IOInfo
    global_reg_name: str

    def __init__(
        self,
        section_id: UUID,
        qubit_to_index: dict[SingleQubit, int],
        io_info: IOInfo,
        global_reg_name: str,
    ) -> None:
        """Construct QubitDeclarationToAlias.

        :param section_id: The UUID of the currently visited section.
        :param qubit_to_index: Map qubits to the indexes in the global reg.
        :param io_info: The IOInfo for the current section.
        """
        self.section_id = section_id
        self.qubit_to_index = qubit_to_index
        self.io_info = io_info
        self.global_reg_name = global_reg_name

    def id_to_qubit(self, id: int) -> SingleQubit:
        """Create :class:`app.processing.merging.connections.SingleQubit` for encountered id."""
        return SingleQubit(self.section_id, id)

    def visit_QubitDeclaration(self, node: QubitDeclaration) -> QASMNode:
        """Replace qubit declaration with alias to leqo_reg."""
        name = node.qubit.name
        ids = self.io_info.declaration_to_ids[name]
        reg_indexes = [self.qubit_to_index[self.id_to_qubit(id)] for id in ids]
        result = AliasStatement(
            Identifier(name),
            # ignore type cause of bug in openqasm3.ast:
            # IndexExpression is allowed as value in AliasStatement
            IndexExpression(  # type: ignore
                Identifier(self.global_reg_name),
                DiscreteSet([IntegerLiteral(index) for index in reg_indexes]),
            ),
        )
        result.annotations = node.annotations
        return result


def get_equiv_classes(graph: ProgramGraph) -> dict[SingleQubit, set[SingleQubit]]:
    """Iterate all nodes to get all existing qubits."""
    qubits = {}
    for nd in graph.nodes():
        section = graph.get_data_node(nd).info
        for qubit_id in section.io.id_to_info:
            qubit = SingleQubit(section.id, qubit_id)
            qubits[qubit] = {qubit}
    return qubits


def connect_qubits(graph: ProgramGraph, global_reg_name: str) -> int:
    """Connect qubits by replacing declarations with aliases.

    1. Collects all qubits from sections
    2. Iterate all edges to create equivalence classes of qubits
    3. Give every equivalence classes an index
    4. Replace all qubit declarations with alias to global reg based on index.

    :param graph: The :class:`app.processing.graph.ProgramGraph` to be changed in-place.
    :return: The size of the global reg.
    """
    equiv_classes = get_equiv_classes(graph)
    for source_node, target_node in graph.edges():
        edges = graph.get_data_edges(source_node, target_node)
        source_section = graph.get_data_node(source_node).info
        target_section = graph.get_data_node(target_node).info
        source_ids = []
        target_ids = []
        for edge in edges:
            match edge:
                case IOConnection():
                    edge_source_ids = source_section.io.output_to_ids.get(
                        edge.source[1],
                    )
                    edge_target_ids = target_section.io.input_to_ids.get(
                        edge.target[1],
                    )
                    if edge_source_ids is None:
                        msg = f"Unsupported: Output with index {edge.source[1]} from {edge.source[0].name} modeled, but no such annotation."
                        raise UnsupportedOperation(msg)
                    if edge_target_ids is None:
                        msg = f"Unsupported: Input with index {edge.target[1]} into {edge.target[0].name} modeled, but no such annotation."
                        raise UnsupportedOperation(msg)
                    if len(edge_source_ids) != len(edge_target_ids):
                        msg = f"Mismatched size in model connection between {source_node.name} and {target_node.name}"
                        raise UnsupportedOperation(msg)
                    source_ids.extend(edge_source_ids)
                    target_ids.extend(edge_target_ids)
                case AncillaConnection():
                    source_ids.extend(edge.source[1])
                    target_ids.extend(edge.target[1])
        for s_id, t_id in zip(source_ids, target_ids, strict=True):
            source_qubit = SingleQubit(source_section.id, s_id)
            target_qubit = SingleQubit(target_section.id, t_id)
            # merge sets and let all qubits point to that set
            merged_equiv = equiv_classes[source_qubit]
            merged_equiv.update(equiv_classes[target_qubit])
            for qubit in equiv_classes[target_qubit]:
                # we don't need to update qubits in source_qubit-set, because we change in-place
                equiv_classes[qubit] = merged_equiv

    reg_index = 0
    qubit_to_reg_index: dict[SingleQubit, int] = {}
    while len(equiv_classes) > 0:
        some_qubit = next(iter(equiv_classes))
        equiv_class = equiv_classes[some_qubit]
        for qubit in equiv_class:
            _ = equiv_classes.pop(qubit)
            qubit_to_reg_index[qubit] = reg_index
        reg_index += 1

    for nd in graph.nodes():
        node = graph.get_data_node(nd)
        QubitDeclarationToAlias(
            node.info.id,
            qubit_to_reg_index,
            node.info.io,
            global_reg_name,
        ).visit(
            node.implementation,
        )

    return reg_index

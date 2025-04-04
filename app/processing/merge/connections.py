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
from app.processing.graph import IOInfo, ProgramGraph

GLOBAL_REG_NAME = "leqo_reg"


@dataclass(frozen=True)
class SingleQubit:
    section_id: UUID
    id_in_section: int

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SingleQubit):
            return NotImplemented
        return (self.section_id, self.id_in_section) < (
            other.section_id,
            other.id_in_section,
        )


class QubitDeclarationToAlias(LeqoTransformer[None]):
    """Replace all qubit declarations with alias to global qubit-reg."""

    section_id: UUID
    qubit_to_index: dict[SingleQubit, int]
    io_info: IOInfo

    def __init__(
        self,
        section_id: UUID,
        qubit_to_index: dict[SingleQubit, int],
        io_info: IOInfo,
    ) -> None:
        self.section_id = section_id
        self.qubit_to_index = qubit_to_index
        self.io_info = io_info

    def id_to_qubit(self, id: int) -> SingleQubit:
        return SingleQubit(self.section_id, id)

    def visit_QubitDeclaration(self, node: QubitDeclaration) -> QASMNode:
        name = node.qubit.name
        ids = self.io_info.declaration_to_id[name]
        reg_indexes = [self.qubit_to_index[self.id_to_qubit(id)] for id in ids]
        result = AliasStatement(
            Identifier(name),
            # ignore type cause of bug in openqasm3.ast:
            # IndexExpression is allowed as value in AliasStatement
            IndexExpression(  # type: ignore
                Identifier(GLOBAL_REG_NAME),
                DiscreteSet([IntegerLiteral(index) for index in reg_indexes]),
            ),
        )
        result.annotations = node.annotations
        return result


def get_all_qubits(graph: ProgramGraph) -> set[SingleQubit]:
    qubits = set()
    for nd in graph.nodes():
        section = graph.get_data_node(nd).info
        for qubit_id in section.io.id_to_info:
            qubits.add(SingleQubit(section.id, qubit_id))
    return qubits


def connect_qubits(graph: ProgramGraph) -> None:
    qubits = get_all_qubits(graph)
    equiv_classes: dict[SingleQubit, set[SingleQubit]] = {q: {q} for q in qubits}
    for source_node, target_node in graph.edges():
        edge = graph.get_data_edge(source_node, target_node)
        source_section = graph.get_data_node(source_node).info
        target_section = graph.get_data_node(target_node).info
        source_ids = source_section.io.output_to_ids[edge.source[1]]
        target_ids = target_section.io.input_to_ids[edge.target[1]]
        if len(source_ids) != len(target_ids):
            msg = f"Mismatched size in model connection between {source_node.name} and {target_node.name}"
            raise UnsupportedOperation(msg)
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
    qubit_list = sorted(qubits)
    # NOTE: design choice:
    # Use list or set for this?
    # Pros for set: already there, faster
    # Pros for list: deterministic result (good for testing), raises error on remove if element not there
    # Choice: use list for now (test won't work otherwise)
    while len(qubit_list) > 0:
        some_qubit = qubit_list[0]
        equiv_class = equiv_classes[some_qubit]
        for qubit in equiv_class:
            qubit_list.remove(qubit)
            qubit_to_reg_index[qubit] = reg_index
        reg_index += 1

    for nd in graph.nodes():
        node = graph.get_data_node(nd)
        QubitDeclarationToAlias(node.info.id, qubit_to_reg_index, node.info.io).visit(
            node.implementation,
        )

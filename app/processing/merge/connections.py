from dataclasses import dataclass
from io import UnsupportedOperation
from uuid import UUID

from app.processing.graph import ProgramGraph


@dataclass(frozen=True)
class SingleQubit:
    section_id: UUID
    id_in_section: int


def connect_qubits(graph: ProgramGraph) -> None:
    qubits = set()
    for nd in graph.nodes():
        section = graph.get_data_node(nd).info
        for qubit in section.io.id_to_info:
            qubits.add(SingleQubit(section.id, qubit))

    equiv_class_counter = 0
    equiv_classes: dict[SingleQubit, int | None] = {}
    for source_node, target_node in graph.edges():
        breakpoint()
        edge = graph.get_data_edge(source_node, target_node)
        source = graph.get_data_node(source_node).info
        target = graph.get_data_node(target_node).info
        if len(source.io.output_to_ids[edge.source[1]]) != len(
            target.io.input_to_ids[edge.target[1]],
        ):
            msg = f"Mismatched size in model connection between {source_node.name} and {target_node.name}"
            raise UnsupportedOperation(msg)

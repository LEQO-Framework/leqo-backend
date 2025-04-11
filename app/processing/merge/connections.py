from dataclasses import dataclass
from io import UnsupportedOperation
from uuid import UUID

from openqasm3.ast import (
    AliasStatement,
    ClassicalDeclaration,
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
    ClassicalIOInstance,
    IOConnection,
    IOInfo,
    ProgramGraph,
    QubitIOInstance,
)


@dataclass(frozen=True)
class SingleQubit:
    """Give an qubit a unique ID in the whole program.

    Combines section_id and qubit id (of that single section).
    """

    section_id: UUID
    id_in_section: int


class ApplyConnectionsTransformer(LeqoTransformer[None]):
    """Replace all qubit declarations with alias to global qubit-reg."""

    section_id: UUID
    io_info: IOInfo
    global_reg_name: str
    qubit_to_index: dict[SingleQubit, int]
    classical_declaration_to_alias: dict[str, str]

    def __init__(
        self,
        section_id: UUID,
        io_info: IOInfo,
        global_reg_name: str,
        qubit_to_index: dict[SingleQubit, int],
        classical_declaration_to_alias: dict[str, str],
    ) -> None:
        """Construct QubitDeclarationToAlias.

        :param section_id: The UUID of the currently visited section.
        :param io_info: The IOInfo for the current section.
        :param global_reg_name: The name to use for global qubit register.
        :param qubit_to_index: Map qubits to the indexes in the global reg.
        :param classical_declaration_to_alias: Map declaration names to alias to use.
        """
        self.section_id = section_id
        self.io_info = io_info
        self.global_reg_name = global_reg_name
        self.qubit_to_index = qubit_to_index
        self.classical_declaration_to_alias = classical_declaration_to_alias

    def id_to_qubit(self, id: int) -> SingleQubit:
        """Create :class:`app.processing.merging.connections.SingleQubit` for encountered id."""
        return SingleQubit(self.section_id, id)

    def visit_QubitDeclaration(self, node: QubitDeclaration) -> QASMNode:
        """Replace qubit declaration with alias to leqo_reg."""
        name = node.qubit.name
        ids = self.io_info.qubits.declaration_to_ids[name]
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

    def visit_ClassicalDeclaration(self, node: ClassicalDeclaration) -> QASMNode:
        return AliasStatement(
            node.identifier,
            Identifier(self.classical_declaration_to_alias[node.identifier.name]),
        )


class Connections:
    graph: ProgramGraph
    global_reg_name: str
    equiv_classes: dict[SingleQubit, set[SingleQubit]]
    classical_declaration_to_alias: dict[str, str]

    @staticmethod
    def get_equiv_classes(graph: ProgramGraph) -> dict[SingleQubit, set[SingleQubit]]:
        """Iterate all nodes to get all existing qubits."""
        qubits = {}
        for nd in graph.nodes():
            section = graph.get_data_node(nd).info
            for qubit_ids in section.io.qubits.declaration_to_ids.values():
                for qubit_id in qubit_ids:
                    qubit = SingleQubit(section.id, qubit_id)
                    qubits[qubit] = {qubit}
        return qubits

    def __init__(self, graph: ProgramGraph, global_reg_name: str) -> None:
        self.graph = graph
        self.global_reg_name = global_reg_name
        self.equiv_classes = self.get_equiv_classes(graph)
        self.classical_declaration_to_alias = {}

    def handle_qubit_connection(
        self,
        output: QubitIOInstance,
        input: QubitIOInstance,
        src_sec_id: UUID,
        target_sec_id: UUID,
    ) -> None:
        output_size, input_size = len(output.ids), len(input.ids)
        if output_size != input_size:
            msg = f"""Unsupported: Mismatched sizes in IOConnection of type qubits-register

            output {output.name} has size {output_size}
            input {input.name} has size {input_size}
            """
            raise UnsupportedOperation(msg)
        for s_id, t_id in zip(output.ids, input.ids, strict=True):
            source_qubit = SingleQubit(src_sec_id, s_id)
            target_qubit = SingleQubit(target_sec_id, t_id)
            # merge sets and let all qubits point to that set
            merged_equiv = self.equiv_classes[source_qubit]
            merged_equiv.update(self.equiv_classes[target_qubit])
            for qubit in self.equiv_classes[target_qubit]:
                # we don't need to update qubits in source_qubit-set, because we change in-place
                self.equiv_classes[qubit] = merged_equiv

    def handle_classical_connection(
        self,
        output: ClassicalIOInstance,
        input: ClassicalIOInstance,
    ) -> None:
        if input.type != output.type:
            msg = f"""Unsupported: Mismatched types in IOConnection

            output {output.name} has type {output.type}
            input {input.name} has type {input.type}
            """
            raise UnsupportedOperation(msg)
        if input.size != output.size:
            msg = f"""Unsupported: Mismatched sizes in IOConnection of type {output.size}

            output {output.name} has size {output.size}
            input {input.name} has size {input.size}
            """
            raise UnsupportedOperation(msg)
        self.classical_declaration_to_alias[input.name] = output.name

    def handle_connection(
        self,
        edge: IOConnection | AncillaConnection,
    ) -> None:
        source_section = self.graph.get_data_node(edge.source[0]).info
        target_section = self.graph.get_data_node(edge.target[0]).info
        match edge:
            case IOConnection():
                output = source_section.io.outputs.get(edge.source[1])
                input = target_section.io.inputs.get(edge.target[1])
                if output is None:
                    msg = f"""Unsupported: Missing output index in connection

                    Index {edge.source[1]} from {edge.source[0].name} modeled,
                    but no such annotation was found.
                    """
                    raise UnsupportedOperation(msg)
                if input is None:
                    msg = f"""Unsupported: Missing input index in connection

                    Index {edge.target[1]} from {edge.target[0].name} modeled,
                    but no such annotation was found.
                    """
                    raise UnsupportedOperation(msg)
                match output, input:
                    case QubitIOInstance(), QubitIOInstance():
                        self.handle_qubit_connection(
                            output,
                            input,
                            source_section.id,
                            target_section.id,
                        )
                    case ClassicalIOInstance(), ClassicalIOInstance():
                        self.handle_classical_connection(output, input)
                    case _:
                        msg = f"""Unsupported: Try to connect qubit with classical

                        Index {edge.target[1]} from {edge.target[0].name} tries to
                        connect to index {edge.source[1]} from {edge.target[0].name}
                        """
                        raise UnsupportedOperation(msg)
            case AncillaConnection():
                self.handle_qubit_connection(
                    QubitIOInstance("__ancilla__", edge.source[1]),
                    QubitIOInstance("__ancilla__", edge.target[1]),
                    source_section.id,
                    target_section.id,
                )

    def apply(self) -> int:
        for source_node, target_node in self.graph.edges():
            edges = self.graph.get_data_edges(source_node, target_node)
            for edge in edges:
                self.handle_connection(edge)

        reg_index = 0
        qubit_to_reg_index: dict[SingleQubit, int] = {}
        while len(self.equiv_classes) > 0:
            some_qubit = next(iter(self.equiv_classes))
            equiv_class = self.equiv_classes[some_qubit]
            for qubit in equiv_class:
                _ = self.equiv_classes.pop(qubit)
                qubit_to_reg_index[qubit] = reg_index
            reg_index += 1

        for nd in self.graph.nodes():
            node = self.graph.get_data_node(nd)
            ApplyConnectionsTransformer(
                node.info.id,
                node.info.io,
                self.global_reg_name,
                qubit_to_reg_index,
                self.classical_declaration_to_alias,
            ).visit(
                node.implementation,
            )

        return reg_index

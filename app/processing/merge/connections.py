"""
Connect input/output by modifying the AST based on :class:`~app.processing.graph.IOInfo`.
"""

from dataclasses import dataclass
from textwrap import dedent
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
    ProcessedProgramNode,
    ProgramGraph,
    QubitInfo,
    QubitIOInstance,
)
from app.processing.merge.utils import MergeException
from app.utils import save_generate_implementation_node


@dataclass(frozen=True, order=True)
class SingleQubit:
    """
    Give a qubit a unique ID in the whole graph.

    :param section_id: The UUID of the section the qubit occurred in.
    :param id_in_section: The Qubit ID based on the declaration order in the section.
    """

    section_id: UUID
    id_in_section: int


class ApplyConnectionsTransformer(LeqoTransformer[None]):
    """
    Replace qubit declarations and classical inputs with aliases.

    :param section_id: The UUID of the currently visited section.
    :param io_info: The IOInfo for the current section.
    :param qubit_info: The QubitInfo for the current section.
    :param global_reg_name: The name to use for the global qubit register.
    :param qubit_to_index: Map qubits to the indexes in the global reg.
    :param classical_input_to_output: Map classical declaration names to aliases to use.
    """

    section_id: UUID
    io_info: IOInfo
    qubit_info: QubitInfo
    global_reg_name: str
    qubit_to_index: dict[SingleQubit, int]
    classical_input_to_output: dict[str, str]

    def __init__(  # noqa: PLR0913
        self,
        section_id: UUID,
        io_info: IOInfo,
        qubit_info: QubitInfo,
        global_reg_name: str,
        qubit_to_index: dict[SingleQubit, int],
        classical_input_to_output: dict[str, str],
    ) -> None:
        self.section_id = section_id
        self.io_info = io_info
        self.qubit_info = qubit_info
        self.global_reg_name = global_reg_name
        self.qubit_to_index = qubit_to_index
        self.classical_input_to_output = classical_input_to_output

    def id_to_qubit(self, id: int) -> SingleQubit:
        """
        Create a :class:`~app.processing.merging.connections.SingleQubit` for the encountered ID.
        """
        return SingleQubit(self.section_id, id)

    def visit_QubitDeclaration(self, node: QubitDeclaration) -> QASMNode:
        """
        Replace qubit declaration with alias to leqo_reg.
        """
        name = node.qubit.name
        ids = self.qubit_info.declaration_to_ids[name]
        reg_indexes = [self.qubit_to_index[self.id_to_qubit(id)] for id in ids]
        # the 'type: ignore' is because of a bug in the openqasm3 module:
        # IndexExpression is allowed as value in AliasStatement (as can be seen by parsed input)
        if node.size is None:
            if len(reg_indexes) != 1:
                msg = f"Critical Internal Error: Expected exactly one qubit index for {node.qubit.name} found {reg_indexes}"
                raise RuntimeError(msg)
            result = AliasStatement(
                Identifier(name),
                IndexExpression(  # type: ignore
                    Identifier(self.global_reg_name),
                    [IntegerLiteral(reg_indexes[0])],
                ),
            )
        else:
            result = AliasStatement(
                Identifier(name),
                IndexExpression(  # type: ignore
                    Identifier(self.global_reg_name),
                    DiscreteSet([IntegerLiteral(index) for index in reg_indexes]),
                ),
            )
        result.annotations = node.annotations
        return result

    def visit_ClassicalDeclaration(self, node: ClassicalDeclaration) -> QASMNode:
        """
        Replace classical declaration with alias to output if it is an input.
        """
        name = node.identifier.name
        if name not in self.classical_input_to_output:
            return self.generic_visit(node)
        result = AliasStatement(
            node.identifier,
            Identifier(self.classical_input_to_output[name]),
        )
        result.annotations = node.annotations
        return result


class _Connections:
    """
    Helper class for creating connections in a graph.

    Not intended to be constructed by hand,
    usage over :class:`~app.processing.merging.connections.connect_qubits`

    :param graph: The graph to modify in place.
    :param global_reg_name: The name of the qubit reg to use in aliases.
    :param input: Optional input node: don't modify it + IDs in the order of the declarations in this node.
    :param equiv_classes: Equivalence classes of qubits based on connections.
    :param classical_input_to_output: Specify classical connections via identifier mapping: input -> output.
    """

    graph: ProgramGraph
    global_reg_name: str
    input: ProcessedProgramNode | None
    equiv_classes: dict[SingleQubit, set[SingleQubit]]
    classical_input_to_output: dict[str, str]

    @staticmethod
    def get_equiv_classes(graph: ProgramGraph) -> dict[SingleQubit, set[SingleQubit]]:
        """
        Get a dict of all qubits pointing to a set containing themselves.
        """
        equiv_classes = {}
        for node in graph.nodes():
            processed = graph.get_data_node(node)
            for qubit_ids in processed.qubit.declaration_to_ids.values():
                for qubit_id in qubit_ids:
                    qubit = SingleQubit(processed.id, qubit_id)
                    equiv_classes[qubit] = {qubit}
        return equiv_classes

    def __init__(
        self,
        graph: ProgramGraph,
        global_reg_name: str,
        input: ProcessedProgramNode | None = None,
    ) -> None:
        self.graph = graph
        self.global_reg_name = global_reg_name
        self.input = input
        self.equiv_classes = self.get_equiv_classes(graph)
        self.classical_input_to_output = {}

    def handle_qubit_connection(
        self,
        output: QubitIOInstance,
        input: QubitIOInstance,
        src_sec_id: UUID,
        target_sec_id: UUID,
    ) -> None:
        """
        Merge qubit equivalence classes of connected qubits.
        """
        output_type, input_type = output.type, input.type
        if output_type != input_type:
            msg = f"Unsupported: Mismatched types in IOConnection {output_type} != {input_type}"
            raise MergeException(msg)
        output_ids = output.ids if isinstance(output.ids, list) else [output.ids]
        input_ids = input.ids if isinstance(input.ids, list) else [input.ids]
        for s_id, t_id in zip(output_ids, input_ids, strict=True):
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
        """
        Let input point to output in classical connection.
        """
        if input.type != output.type:
            msg = dedent(f"""\
                Unsupported: Mismatched types in IOConnection

                output {output.name} has type {output.type}
                input {input.name} has type {input.type}
                """)
            raise MergeException(msg)
        if input.name in self.classical_input_to_output:
            msg = dedent(f"""\
                Unsupported: Multiple inputs into classical

                Both {self.classical_input_to_output[input.name]} and {output.name}
                are input to {input.name} but only one is allowed.
                """)
            raise MergeException(msg)
        self.classical_input_to_output[input.name] = output.name

    def handle_connection(
        self,
        edge: IOConnection | AncillaConnection,
    ) -> None:
        """
        Handle connection based on type.
        """
        processed_source = self.graph.get_data_node(edge.source[0])
        processed_target = self.graph.get_data_node(edge.target[0])
        match edge:
            case IOConnection():
                output = processed_source.io.outputs.get(edge.source[1])
                input = processed_target.io.inputs.get(edge.target[1])
                if output is None:
                    msg = dedent(f"""\
                        Unsupported: Missing output index in connection

                        Index {edge.source[1]} from {edge.source[0].name} modeled,
                        but no such annotation was found.
                        """)
                    node = self.graph.node_data[edge.source[0]]
                    raise MergeException(
                        msg,
                        save_generate_implementation_node(
                            node.raw.name, node.implementation
                        ),
                    )
                if input is None:
                    msg = dedent(f"""\
                        Unsupported: Missing input index in connection

                        Index {edge.target[1]} from {edge.target[0].name} modeled,
                        but no such annotation was found.
                        """)
                    node = self.graph.node_data[edge.target[0]]
                    raise MergeException(
                        msg,
                        save_generate_implementation_node(
                            node.raw.name, node.implementation
                        ),
                    )

                match output, input:
                    case QubitIOInstance(), QubitIOInstance():
                        self.handle_qubit_connection(
                            output,
                            input,
                            processed_source.id,
                            processed_target.id,
                        )
                    case ClassicalIOInstance(), ClassicalIOInstance():
                        self.handle_classical_connection(output, input)
                    case _:
                        msg = dedent(f"""\
                            Unsupported: Try to connect qubit with classical

                            Index {edge.target[1]} from {edge.target[0].name} tries to
                            connect to index {edge.source[1]} from {edge.target[0].name}
                            """)
                        raise MergeException(msg)
            case AncillaConnection():
                self.handle_qubit_connection(
                    # the name __ancilla__ is only used in errors
                    QubitIOInstance("__ancilla__", edge.source[1]),
                    QubitIOInstance("__ancilla__", edge.target[1]),
                    processed_source.id,
                    processed_target.id,
                )

    def collect_qubit_to_reg_with_input(
        self,
    ) -> tuple[dict[SingleQubit, int], int]:
        """
        Construct global register indexes from equivalence classes with an input node.

        Create a unique index for every equivalence class and let all qubits inside point to it.
        We want the indexes of the qubits in the input node to be in ascending order (based on declarations).
        This is important, as we want to construct the reg from those declarations.

        :return: A dict, mapping qubit IDs to reg index and total size of the reg.
        """
        if self.input is None:
            raise RuntimeError

        reg_index = 0
        qubit_to_reg_index: dict[SingleQubit, int] = {}
        for declaration_ids in self.input.qubit.declaration_to_ids.values():
            for id in declaration_ids:
                equiv_class = self.equiv_classes[SingleQubit(self.input.id, id)]
                for qubit in equiv_class:
                    try:
                        _ = self.equiv_classes.pop(qubit)
                    except KeyError as e:
                        msg = "Two qubits in input share the same equiv_class."
                        raise RuntimeError(msg) from e
                    qubit_to_reg_index[qubit] = reg_index
                reg_index += 1

        remaining = sorted(
            self.equiv_classes.keys(),
        )  # minimize the change to get different endif_nodes
        while len(remaining) > 0:
            some_qubit = remaining[0]
            equiv_class = self.equiv_classes[some_qubit]
            for qubit in equiv_class:
                remaining.remove(qubit)
                qubit_to_reg_index[qubit] = reg_index
            reg_index += 1

        return (qubit_to_reg_index, reg_index)

    def collect_qubit_to_reg_without_input(
        self,
    ) -> tuple[dict[SingleQubit, int], int]:
        """
        Construct global register indexes from equivalence classes without an input node.

        Create a unique index for every equivalence class and let all qubits inside point to it.

        :return: A dict, mapping qubit IDs to reg index and total size of the reg.
        """
        if self.input is not None:
            raise RuntimeError

        reg_index = 0
        qubit_to_reg_index: dict[SingleQubit, int] = {}
        while len(self.equiv_classes) > 0:
            some_qubit = next(iter(self.equiv_classes))
            equiv_class = self.equiv_classes[some_qubit]
            for qubit in equiv_class:
                _ = self.equiv_classes.pop(qubit)
                qubit_to_reg_index[qubit] = reg_index
            reg_index += 1

        return (qubit_to_reg_index, reg_index)

    def apply(self) -> int:
        """
        Apply the connections to the graph.

        :return: The size of the global qubit register.
        """
        for source_node, target_node in self.graph.edges():
            edges = self.graph.get_data_edges(source_node, target_node)
            for edge in edges:
                try:
                    self.handle_connection(edge)
                except MergeException as exc:
                    if exc.node is None:
                        node = self.graph.node_data[edge.source[0]]
                        exc.node = save_generate_implementation_node(
                            node.raw.name, node.implementation
                        )
                    raise exc

        qubit_to_reg_index: dict[SingleQubit, int]
        reg_index: int
        if self.input is not None:
            qubit_to_reg_index, reg_index = self.collect_qubit_to_reg_with_input()
        else:
            qubit_to_reg_index, reg_index = self.collect_qubit_to_reg_without_input()

        for nd in self.graph.nodes():
            if self.input is not None and self.input.raw == nd:
                continue  # don't modify the input-node!
            node = self.graph.get_data_node(nd)
            ApplyConnectionsTransformer(
                node.id,
                node.io,
                node.qubit,
                self.global_reg_name,
                qubit_to_reg_index,
                self.classical_input_to_output,
            ).visit(
                node.implementation,
            )

        return reg_index


def connect_qubits(
    graph: ProgramGraph,
    global_reg_name: str,
    input: ProcessedProgramNode | None = None,
) -> int:
    """
    Apply connections to the graph.

    :param graph: The graph to modify in place.
    :param global_reg_name: The name of the qubit reg to use in aliases.
    :param input: Optional input node: don't modify it + IDs in the order of the declarations in this node.
    :return: The size of the global qubit register.
    """
    return _Connections(graph, global_reg_name, input).apply()

"""
Allow for smaller inputs by reducing the size of the type in the AST and parsed info.
"""

from __future__ import annotations

from copy import deepcopy

from openqasm3.ast import (
    AliasStatement,
    Annotation,
    BitType,
    ClassicalDeclaration,
    Concatenation,
    FloatType,
    Identifier,
    IntegerLiteral,
    IntType,
    QASMNode,
    QubitDeclaration,
)

from app.openqasm3.visitor import LeqoTransformer
from app.transformation_manager.graph import (
    ClassicalIOInstance,
    ProcessedProgramNode,
    QubitIOInstance,
)
from app.transformation_manager.pre.utils import PreprocessingException, parse_io_annotation


class CreateUnseenNamesVisitor(LeqoTransformer[None]):
    """
    Keep track of all identifier in an AST to create new ones.
    """

    seen: set[str]

    def __init__(self) -> None:
        super().__init__()
        self.seen = set()

    def visit_Identifier(self, node: Identifier) -> QASMNode:
        """
        Collect identifier names.
        """
        self.seen.add(node.name)
        return self.generic_visit(node)

    @staticmethod
    def __increment_or_add_counter_str(name: str) -> str:
        """
        Increment the number at the end of a string by one or append '_0'.
        """
        prefix = ""
        maybe_number = name
        while True:
            if maybe_number == "":
                return prefix + "_0"
            if maybe_number.isdecimal():
                return prefix + str(int(maybe_number) + 1)
            prefix, maybe_number = prefix + maybe_number[0], maybe_number[1:]

    def generate_new_name(self, name: str) -> str:
        """
        Generate a new unused identifier name.
        """
        while name in self.seen:
            name = self.__increment_or_add_counter_str(name)
        self.seen.add(name)
        return name


class SizeCastTransformer(LeqoTransformer[None]):
    """
    Apply the size-reduction casts.

    :param processed: The ProcessedProgramNode to be modified in-place.
    :param requested_sizes: Specifying the required sizes for the input indexes.
    :param name_factory: Used for getting new unseen names.
    """

    processed: ProcessedProgramNode
    requested_sizes: dict[int, int | None]
    name_factory: CreateUnseenNamesVisitor

    def __init__(
        self,
        processed: ProcessedProgramNode,
        requested_sizes: dict[int, int | None],
        name_factory: CreateUnseenNamesVisitor,
    ) -> None:
        super().__init__()
        self.processed = processed
        self.requested_sizes = requested_sizes
        self.name_factory = name_factory

    @staticmethod
    def get_input_index(annotations: list[Annotation]) -> None | int:
        """
        Parse annotations for input with index.
        """
        for annotation in annotations:
            if annotation.keyword.startswith("leqo.input"):
                return parse_io_annotation(annotation)
        return None

    @staticmethod
    def raise_if_cast_to_bigger(
        requested: int | None,
        actual: int | None,
        ioinstance: QubitIOInstance | ClassicalIOInstance,
    ) -> None:
        if (requested is not None and actual is None) or (
            requested is not None and actual is not None and requested > actual
        ):
            msg = f"Try to make {ioinstance} bigger, only smaller is possible."
            raise PreprocessingException(msg)

    def visit_ClassicalDeclaration(
        self,
        node: ClassicalDeclaration,
    ) -> QASMNode | list[QASMNode]:
        """
        Reduce size of a classical input.

        - Handle int/float:
            This is done by reducing the size in the declaration and changing its name.
            Then the old name is declared with old size and assigned to the new name.

            This seems to be the way that Openqasm 3 handles implicit casts,
            but there was no concrete example of this in the specification.

            .. warning::

                Qiskit does not support the declaration of int/float yet.
                Making this currently unusable.

        - Handle bit:
            Similar to qubits, declare a dummy register to be concatenated to
            the now smaller input.
            This is done in little endian order.

            .. warning::

                The dummy register is not initialized to zero as this is
                unsupported by qiskit. It is assumed that they are 0 by default.
        """
        if not isinstance(node.type, IntType | FloatType | BitType):
            return node

        index = self.get_input_index(node.annotations)
        if index is None or index not in self.requested_sizes:
            return node

        ioinstance = self.processed.io.inputs[index]
        if not isinstance(ioinstance, ClassicalIOInstance):
            msg = "IO-Info specifies qubit input for classic input in AST."
            raise RuntimeError(msg)

        requested = self.requested_sizes[index]
        actual = ioinstance.type.size
        self.raise_if_cast_to_bigger(requested, actual, ioinstance)

        if requested == actual:
            return node
        assert actual is not None

        old_name = node.identifier.name
        new_input_name = self.name_factory.generate_new_name(node.identifier.name)

        # update IO-Info in-place
        ioinstance.name = new_input_name
        ioinstance.type = ioinstance.type.with_size(requested)

        match node.type:
            case IntType() | FloatType():
                if requested is None:
                    msg = "can't cast int/float to None"
                    raise PreprocessingException(msg)

                # create new declaration with old name + size pointing to new
                new_input_node = ClassicalDeclaration(
                    type=deepcopy(node.type),
                    identifier=deepcopy(node.identifier),
                    init_expression=Identifier(new_input_name),
                )

                # modify old node in-place (keep annotations)
                node.identifier.name = new_input_name
                node.type.size = IntegerLiteral(requested)

                return [
                    node,
                    new_input_node,
                ]

            case BitType():
                statements: list[QASMNode] = []

                # modify old node in-place (keep annotations)
                node.identifier.name = new_input_name
                node.type = BitType(
                    None if requested is None else IntegerLiteral(requested)
                )
                statements.append(node)

                # if casting from array -> single: intermediate bit reg with size 1 is needed
                bit_reg1_name: str | None = None
                if requested is None:
                    bit_reg1_name = self.name_factory.generate_new_name(
                        node.identifier.name
                    )
                    statements.append(
                        ClassicalDeclaration(
                            BitType(IntegerLiteral(1)),
                            Identifier(bit_reg1_name),
                            Identifier(new_input_name),
                        )
                    )
                    requested = 1

                # create new dummy node for remaining bits
                new_dummy_name = self.name_factory.generate_new_name(old_name)
                statements.append(
                    ClassicalDeclaration(
                        BitType(IntegerLiteral(actual - requested)),
                        Identifier(new_dummy_name),
                        None,
                    )
                )

                # create alias with old name pointing to concatenation
                statements.append(
                    AliasStatement(
                        target=Identifier(old_name),
                        value=Concatenation(
                            Identifier(
                                new_input_name
                                if bit_reg1_name is None
                                else bit_reg1_name
                            ),
                            Identifier(new_dummy_name),
                        ),
                    )
                )

                return statements

    def visit_QubitDeclaration(
        self,
        node: QubitDeclaration,
    ) -> QASMNode | list[QASMNode]:
        """
        Reduce size of a qubit input.

        This is done by splitting the old declaration in two:

        - one for the linked qubits
        - one for the clean ancillas

        Both are created with new identifiers.
        Then the old name is aliased to a concatenation of the previous variables.
        The concatenation uses little endian order.
        """
        index = self.get_input_index(node.annotations)
        if index is None or index not in self.requested_sizes:
            return node

        ioinstance = self.processed.io.inputs[index]
        if not isinstance(ioinstance, QubitIOInstance):
            msg = "IO-Info specifies classic input for qubit input in AST."
            raise RuntimeError(msg)

        requested = self.requested_sizes[index]
        ids = ioinstance.ids
        actual = len(ids) if isinstance(ids, list) else None

        self.raise_if_cast_to_bigger(requested, actual, ioinstance)

        if requested == actual:
            return node
        assert actual is not None
        assert isinstance(ids, list)

        if requested is None:
            msg = """\
            Future Warning: Can't cast qubit-reg to single qubit.

            This is because it is not possible to build a qubit-reg out of single qubits,
            neither in Qiskit nor via the openqasm3 lib.
            In the future, this might work, then it should be handled similar to classic bits.
            """
            raise NotImplementedError(msg)

        old_name = node.qubit.name
        new_input_name = self.name_factory.generate_new_name(old_name)
        new_input_ids, new_ancilla_ids = ids[:requested], ids[requested:]

        # modify old node in-place (keep annotations)
        node.qubit.name = new_input_name
        node.size = IntegerLiteral(requested)

        # create new dummy node for ancillae
        new_ancilla_name = self.name_factory.generate_new_name(old_name)
        new_ancilla_node = QubitDeclaration(
            Identifier(new_ancilla_name),
            size=IntegerLiteral(len(new_ancilla_ids)),
        )

        # create alias with old name pointing to concatenation
        new_alias = AliasStatement(
            target=Identifier(old_name),
            value=Concatenation(
                Identifier(new_input_name),
                Identifier(new_ancilla_name),
            ),
        )

        # update IO-Info in-place
        self.processed.qubit.declaration_to_ids.pop(old_name)
        self.processed.qubit.declaration_to_ids[new_input_name] = new_input_ids
        self.processed.qubit.declaration_to_ids[new_ancilla_name] = new_ancilla_ids
        self.processed.qubit.clean_ids.extend(new_ancilla_ids)
        ioinstance.name = new_input_name
        ioinstance.ids = new_input_ids

        return [node, new_ancilla_node, new_alias]


def size_cast(
    node: ProcessedProgramNode, requested_sizes: dict[int, int | None]
) -> None:
    """
    Reduce the size of inputs in a node.

    :param node: The node to be modified in-place.
    :param requested_sizes: Specifying the sizes to cast to by input index.
    """
    name_factory = CreateUnseenNamesVisitor()
    name_factory.visit(node.implementation)
    SizeCastTransformer(node, requested_sizes, name_factory).visit(node.implementation)

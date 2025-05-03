"""Allow for smaller inputs by reducing the size of the type in the AST and parsed info."""

from __future__ import annotations

from copy import deepcopy
from io import UnsupportedOperation

from openqasm3.ast import (
    AliasStatement,
    Annotation,
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
from app.processing.graph import (
    ClassicalIOInstance,
    ProcessedProgramNode,
    QubitIOInstance,
)
from app.processing.utils import parse_io_annotation


class CreateUnseenNamesVisitor(LeqoTransformer[None]):
    """Keep track of all identifier in an AST to create new ones."""

    seen: set[str]

    def __init__(self) -> None:
        super().__init__()
        self.seen = set()

    def visit_Identifier(self, node: Identifier) -> QASMNode:
        """Collect identifier names."""
        self.seen.add(node.name)
        return self.generic_visit(node)

    @staticmethod
    def __increment_or_add_counter_str(name: str) -> str:
        """Increment the number at the end of a string by one or append '_0'."""
        prefix = ""
        maybe_number = name
        while True:
            if maybe_number == "":
                return prefix + "_0"
            if maybe_number.isdecimal():
                return prefix + str(int(maybe_number) + 1)
            prefix, maybe_number = prefix + maybe_number[0], maybe_number[1:]

    def generate_new_name(self, name: str) -> str:
        """Generate a new unused identifier name."""
        while name in self.seen:
            name = self.__increment_or_add_counter_str(name)
        self.seen.add(name)
        return name


class SizeCastTransformer(LeqoTransformer[None]):
    """Apply the size-reduction casts.

    :param processed: The ProcessedProgramNode to be modified in-place.
    :param requested_sizes: Specifying the required sizes for the input indexes.
    :param name_factory: Used for getting new unseen names.
    """

    processed: ProcessedProgramNode
    requested_sizes: dict[int, int]
    name_factory: CreateUnseenNamesVisitor

    def __init__(
        self,
        processed: ProcessedProgramNode,
        requested_sizes: dict[int, int],
        name_factory: CreateUnseenNamesVisitor,
    ) -> None:
        super().__init__()
        self.processed = processed
        self.requested_sizes = requested_sizes
        self.name_factory = name_factory

    @staticmethod
    def get_input_index(annotations: list[Annotation]) -> None | int:
        """Parse annotations for input with index."""
        for annotation in annotations:
            if annotation.keyword.startswith("leqo.input"):
                return parse_io_annotation(annotation)
        return None

    @staticmethod
    def raise_on_cast_to_bigger(
        ioinstance: QubitIOInstance | ClassicalIOInstance,
    ) -> None:
        msg = f"Try to make {ioinstance} bigger, only smaller is possible."
        raise UnsupportedOperation(msg)

    def visit_ClassicalDeclaration(
        self,
        node: ClassicalDeclaration,
    ) -> QASMNode | list[QASMNode]:
        """Reduce size of a classical input.

        This is done by reducing the size in the declaration and changing its name.
        Then the old name is declared with old size and assigned to the new name.

        This seems to be the way that Openqasm 3 handles implicit casts,
        but there was no concrete example of this in the specification.
        """
        if not isinstance(node.type, IntType | FloatType):
            return node

        index = self.get_input_index(node.annotations)
        if index is None or index not in self.requested_sizes:
            return node

        ioinstance = self.processed.io.inputs[index]
        if not isinstance(ioinstance, ClassicalIOInstance):
            msg = "IO-Info specifies qubit input for classic input in AST."
            raise RuntimeError(msg)

        requested = self.requested_sizes[index]
        actual = ioinstance.type.bit_size
        if requested > actual:
            self.raise_on_cast_to_bigger(ioinstance)

        if requested == actual:
            return node

        old_name = node.identifier.name
        old_type = deepcopy(node.type)
        new_name = self.name_factory.generate_new_name(old_name)

        node.identifier.name = new_name
        node.type.size = IntegerLiteral(requested)
        ioinstance.name = new_name
        ioinstance.type = ioinstance.type.with_bit_size(requested)

        return [
            node,
            ClassicalDeclaration(
                type=old_type,
                identifier=Identifier(old_name),
                init_expression=Identifier(new_name),
            ),
        ]

    def visit_QubitDeclaration(
        self,
        node: QubitDeclaration,
    ) -> QASMNode | list[QASMNode]:
        """Reduce size of a qubit input.

        This is done by splitting the old declaration in two:
        - one for the linked qubits
        - one for the clean ancillas
        Both are created with new identifiers.
        Then the old name is aliased to a concatenation of the previous variables.
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
        actual = len(ids)

        if requested > actual:
            self.raise_on_cast_to_bigger(ioinstance)

        if requested == actual:
            return node

        old_name = node.qubit.name
        new_name_io = self.name_factory.generate_new_name(old_name)
        new_name_ancilla = self.name_factory.generate_new_name(old_name)

        io_ids, ancilla_ids = ids[:requested], ids[requested:]

        node.qubit.name = new_name_io
        node.size = IntegerLiteral(requested)
        self.processed.qubit.declaration_to_ids.pop(old_name)
        self.processed.qubit.declaration_to_ids[new_name_io] = io_ids
        self.processed.qubit.declaration_to_ids[new_name_ancilla] = ancilla_ids
        ioinstance.name = new_name_io
        ioinstance.ids = io_ids
        self.processed.qubit.required_reusable_ids.extend(ancilla_ids)

        return [
            node,
            QubitDeclaration(
                Identifier(new_name_ancilla),
                size=IntegerLiteral(len(ancilla_ids)),
            ),
            AliasStatement(
                target=Identifier(old_name),
                value=Concatenation(
                    Identifier(new_name_io),
                    Identifier(new_name_ancilla),
                ),
            ),
        ]


def size_cast(node: ProcessedProgramNode, requested_sizes: dict[int, int]) -> None:
    """Reduce the size of inputs in a node.

    :param node: The node to be modified in-place.
    :param requested_sizes: Specifying the sizes to cast to by input index.
    """
    name_factory = CreateUnseenNamesVisitor()
    name_factory.visit(node.implementation)
    SizeCastTransformer(node, requested_sizes, name_factory).visit(node.implementation)

from __future__ import annotations

from io import UnsupportedOperation

from openqasm3.ast import (
    AliasStatement,
    Annotation,
    BitType,
    ClassicalDeclaration,
    ClassicalType,
    Concatenation,
    Expression,
    Identifier,
    IndexExpression,
    IntType,
    QASMNode,
    QubitDeclaration,
)

from app.openqasm3.ast import QubitType
from app.openqasm3.visitor import LeqoTransformer
from app.processing.io_info import (
    CombinedIOInfo,
)
from app.processing.pre.io_parser.bits import BitIOInfoBuilder
from app.processing.pre.io_parser.qubits import QubitIOInfoBuilder
from app.processing.pre.io_parser.sized_types import IntIOInfoBuilder
from app.processing.utils import parse_io_annotation


class ParseAnnotationsVisitor(LeqoTransformer[None]):
    """Parse input/output qubits of a single qasm-snippet."""

    io: CombinedIOInfo
    identifier_to_type: dict[str, ClassicalType | QubitType]
    found_input_ids: set[int]
    found_output_ids: set[int]
    qubit_builder: QubitIOInfoBuilder
    bit_builder: BitIOInfoBuilder
    int_builder: IntIOInfoBuilder

    def __init__(self, io: CombinedIOInfo) -> None:
        """Construct the LeqoTransformer."""
        super().__init__()
        self.io = io
        self.identifier_to_type = {}
        self.found_input_ids = set()
        self.found_output_ids = set()
        self.qubit_builder = QubitIOInfoBuilder(io.qubit)
        self.bit_builder = BitIOInfoBuilder(io.bit)
        self.int_builder = IntIOInfoBuilder(io.int)

    def get_declaration_annotation_info(
        self,
        name: str,
        annotations: list[Annotation],
    ) -> tuple[int | None, bool]:
        """Extract annotation info for declaration, throw error on bad usage."""
        input_id: int | None = None
        dirty = False
        for annotation in annotations:
            match annotation.keyword:
                case "leqo.input":
                    if input_id is not None:
                        msg = f"Unsupported: two input annotations over {name}"
                        raise UnsupportedOperation(msg)
                    input_id = parse_io_annotation(annotation)
                case "leqo.dirty":
                    if dirty:
                        msg = f"Unsupported: two dirty annotations over {name}"
                        raise UnsupportedOperation(msg)
                    if (
                        annotation.command is not None
                        and annotation.command.strip() != ""
                    ):
                        msg = f"Unsupported: found {annotation.command} over dirty annotations {name}"
                        raise UnsupportedOperation(msg)
                    dirty = True
                case "leqo.output" | "leqo.reusable":
                    msg = f"Unsupported: {annotation.keyword} annotations over QubitDeclaration {name}"
                    raise UnsupportedOperation(msg)
        if input_id is not None and dirty:
            msg = (
                f"Unsupported: dirty and input annotations over QubitDeclaration {name}"
            )
            raise UnsupportedOperation(msg)
        return input_id, dirty

    def get_alias_annotation_info(
        self,
        name: str,
        annotations: list[Annotation],
    ) -> tuple[int | None, bool]:
        """Extract annotation info for alias, throw error on bad usage."""
        output_id: int | None = None
        reusable = False
        for annotation in annotations:
            match annotation.keyword:
                case "leqo.output":
                    if output_id is not None:
                        msg = f"Unsupported: two output annotations over {name}"
                        raise UnsupportedOperation(msg)
                    output_id = parse_io_annotation(annotation)
                case "leqo.reusable":
                    if reusable:
                        msg = f"Unsupported: two reusable annotations over {name}"
                        raise UnsupportedOperation(msg)
                    if (
                        annotation.command is not None
                        and annotation.command.strip() != ""
                    ):
                        msg = f"Unsupported: found {annotation.command} over reusable annotations {name}"
                        raise UnsupportedOperation(msg)
                    reusable = True
                case "leqo.input" | "leqo.dirty":
                    msg = f"Unsupported: {annotation.keyword} annotations over AliasStatement {name}"
                    raise UnsupportedOperation(msg)
        if output_id is not None and reusable:
            msg = f"Unsupported: input and dirty annotations over AliasStatement {name}"
            raise UnsupportedOperation(msg)
        return (output_id, reusable)

    def get_some_identifier_from_alias(
        self,
        value: Identifier | IndexExpression | Concatenation | Expression,
    ) -> Identifier:
        """Recursively get type of alias expression."""
        match value:
            case IndexExpression():
                if not isinstance(value.collection, Identifier):
                    msg = f"Unsupported expression in alias: {type(value.collection)}"
                    raise TypeError(msg)
                return value.collection
            case Identifier():
                return value
            case Concatenation():
                return self.get_some_identifier_from_alias(value.lhs)
            case Expression():
                msg = f"Unsupported expression in alias: {type(value)}"
                raise UnsupportedOperation(msg)
            case _:
                msg = f"{type(value)} is not implemented as alias expression"
                raise NotImplementedError(msg)

    def update_input_id(self, input_id: int | None) -> None:
        if input_id is not None:
            if input_id in self.found_input_ids:
                msg = f"Unsupported: duplicate input id: {input_id}"
                raise IndexError(msg)
            self.found_input_ids.add(input_id)

    def visit_QubitDeclaration(self, node: QubitDeclaration) -> QASMNode:
        name = node.qubit.name
        input, dirty = self.get_declaration_annotation_info(
            name,
            node.annotations,
        )
        self.update_input_id(input)
        self.identifier_to_type[name] = QubitType()
        self.qubit_builder.handle_declaration(node, input, dirty)
        return self.generic_visit(node)

    def visit_ClassicalDeclaration(self, node: ClassicalDeclaration) -> QASMNode:
        name = node.identifier.name
        input_id, dirty = self.get_declaration_annotation_info(
            name,
            node.annotations,
        )
        self.update_input_id(input_id)
        self.identifier_to_type[name] = node.type

        if dirty:
            msg = f"Unsupported: dirty annotation over non-qubit declaration {name}"
            raise UnsupportedOperation(msg)

        match node.type:
            case BitType():
                self.bit_builder.handle_declaration(node, input_id)
            case IntType():
                self.int_builder.handle_declaration(node, input_id)

        return self.generic_visit(node)

    def visit_AliasStatement(self, node: AliasStatement) -> QASMNode:
        """Parse qubit-alias and their corresponding output annotations."""
        name = node.target.name
        output_id, reusable = self.get_alias_annotation_info(
            name,
            node.annotations,
        )
        if output_id is not None:
            if output_id in self.found_output_ids:
                msg = f"Unsupported: duplicate output id: {output_id}"
                raise IndexError(msg)
            self.found_output_ids.add(output_id)

        found_type = self.identifier_to_type[
            self.get_some_identifier_from_alias(node.value).name
        ]
        self.identifier_to_type[name] = found_type

        match found_type:
            case QubitType():
                self.qubit_builder.handle_alias(node, output_id, reusable)
            case BitType():
                self.bit_builder.handle_alias(node, output_id, reusable)
            case IntType():
                self.int_builder.handle_alias(node, output_id, reusable)
        return self.generic_visit(node)

    @staticmethod
    def raise_on_non_contiguous_range(numbers: set[int], name_of_check: str) -> None:
        """Check if int set is contiguous."""
        for i, j in enumerate(sorted(numbers)):
            if i == j:
                continue
            msg = f"Unsupported: Missing {name_of_check} index {i}, next index was {j}"
            raise IndexError(msg)

    def visit_Program(self, node: QASMNode) -> QASMNode:
        node = self.generic_visit(node)
        self.raise_on_non_contiguous_range(self.found_input_ids, "input")
        self.raise_on_non_contiguous_range(self.found_output_ids, "output")
        self.qubit_builder.finish()
        self.bit_builder.finish()
        self.int_builder.finish()
        return node

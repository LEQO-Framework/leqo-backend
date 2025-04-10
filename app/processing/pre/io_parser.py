from __future__ import annotations

from abc import ABC, abstractmethod
from io import UnsupportedOperation
from itertools import chain
from typing import Any, Generic, TypeVar, override

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
    QASMNode,
    QubitDeclaration,
)

from app.openqasm3.ast import QubitType
from app.openqasm3.visitor import LeqoTransformer
from app.processing.io_info import (
    CombinedIOInfo,
    QubitAnnotationInfo,
    QubitIOInfo,
    RegIOInfo,
    RegSingleInputInfo,
    RegSingleOutputInfo,
)
from app.processing.utils import expr_to_int, parse_io_annotation, parse_qasm_index

T = TypeVar("T")
RT = TypeVar("RT", bound=RegIOInfo[Any])


class IOInfoBuilder(Generic[T], ABC):
    """Abstract class for io info constructors for various types."""

    @abstractmethod
    def handle_declaration(
        self,
        declaration: QubitDeclaration | ClassicalDeclaration,
        input_id: int | None,
        dirty: bool,
    ) -> None:
        msg = "'handle_declaration' called on abstract IOInfoConstructor"
        raise NotImplementedError(msg)

    @abstractmethod
    def handle_alias(
        self,
        alias: AliasStatement,
        output_id: int | None,
        reusable: bool,
    ) -> None:
        msg = "'handle_alias' called on abstract IOInfoConstructor"
        raise NotImplementedError(msg)

    @abstractmethod
    def finish(self) -> T:
        msg = "'finish' called on abstract IOInfoConstructor"
        raise NotImplementedError(msg)


class RegIOInfoBuilder(Generic[RT], IOInfoBuilder[RT], ABC):
    next_id: int
    io: RT
    alias_to_ids: dict[str, list[int]]

    def __init__(self, io: RT) -> None:
        self.next_id = 0
        self.io = io
        self.alias_to_ids = {}

    def identifier_to_ids(self, identifier: str) -> list[int] | None:
        """Get ids via declaration_to_ids or alias_to_ids."""
        result = self.io.declaration_to_ids.get(identifier)
        return self.alias_to_ids.get(identifier) if result is None else result

    def declartion_size_to_ids(self, size: Expression | None) -> list[int]:
        reg_size = expr_to_int(size) if size is not None else 1
        result = []
        for _ in range(reg_size):
            result.append(self.next_id)
            self.next_id += 1
        return result

    def alias_expr_to_ids(
        self,
        value: Identifier | IndexExpression | Concatenation | Expression,
    ) -> list[int] | None:
        """Recursively get IDs list for alias expression."""
        match value:
            case IndexExpression():
                collection = value.collection
                if not isinstance(collection, Identifier):
                    msg = f"Unsupported expression in alias: {type(collection)}"
                    raise TypeError(msg)
                source = self.identifier_to_ids(collection.name)
                if source is None:
                    return None
                indices = parse_qasm_index([value.index], len(source))
                return [source[i] for i in indices]
            case Identifier():
                return self.identifier_to_ids(value.name)
            case Concatenation():
                lhs = self.alias_expr_to_ids(value.lhs)
                rhs = self.alias_expr_to_ids(value.rhs)
                if lhs is None or rhs is None:
                    return None
                return lhs + rhs
            case Expression():
                msg = f"Unsupported expression in alias: {type(value)}"
                raise UnsupportedOperation(msg)
            case _:
                msg = f"{type(value)} is not implemented as alias expression"
                raise NotImplementedError(msg)


class QubitIOInfoBuilder(RegIOInfoBuilder[QubitIOInfo]):
    def __init__(self, io: QubitIOInfo) -> None:
        super().__init__(io)

    @override
    def handle_declaration(
        self,
        declaration: QubitDeclaration | ClassicalDeclaration,
        input_id: int | None,
        dirty: bool,
    ) -> None:
        if not isinstance(declaration, QubitDeclaration):
            msg = (
                f"handle_declaration: expected QubitDeclaration got {type(declaration)}"
            )
            raise TypeError(msg)

        name = declaration.qubit.name
        qubit_ids = self.declartion_size_to_ids(declaration.size)

        for i, qubit_id in enumerate(qubit_ids):
            self.io.id_to_info[qubit_id] = QubitAnnotationInfo(
                input=RegSingleInputInfo(input_id, i) if input_id is not None else None,
                dirty=dirty,
            )
        self.io.declaration_to_ids[name] = qubit_ids

        if input_id is not None:
            self.io.input_to_ids[input_id] = qubit_ids
        elif dirty:
            self.io.dirty_ancillas.extend(qubit_ids)
        else:  # non-input and non-dirty
            self.io.required_ancillas.extend(qubit_ids)

    @override
    def handle_alias(
        self,
        alias: AliasStatement,
        output_id: int | None,
        reusable: bool,
    ) -> None:
        name = alias.target.name

        qubit_ids = self.alias_expr_to_ids(alias.value)
        if qubit_ids is None:
            return
        if len(qubit_ids) == 0:
            msg = f"Unable to resolve IDs of alias {alias}"
            raise RuntimeError(msg)

        self.alias_to_ids[name] = qubit_ids
        if output_id is not None:
            self.io.output_to_ids[output_id] = qubit_ids

        for i, qubit_id in enumerate(qubit_ids):
            current_info = self.io.id_to_info[qubit_id]
            if reusable:
                if current_info.output is not None:
                    msg = f"alias {name} declares output qubit as reusable"
                    raise UnsupportedOperation(msg)
                current_info.reusable = True
                self.io.reusable_ancillas.append(qubit_id)
            elif output_id is not None:
                if current_info.output is not None:
                    msg = f"alias {name} tries to overwrite already declared output"
                    raise UnsupportedOperation(msg)
                if current_info.reusable:
                    msg = f"alias {name} declares output for reusable qubit"
                    raise UnsupportedOperation(msg)
                current_info.output = RegSingleOutputInfo(output_id, i)

    @override
    def finish(self) -> QubitIOInfo:
        returned_dirty = set(self.io.id_to_info.keys())
        returned_dirty.difference_update(
            self.io.reusable_ancillas,
            self.io.reusable_after_uncompute,
            set(chain(*self.io.output_to_ids.values())),
        )
        self.io.returned_dirty_ancillas = sorted(returned_dirty)
        return self.io


class ParseAnnotationsVisitor(LeqoTransformer[None]):
    """Parse input/output qubits of a single qasm-snippet."""

    io: CombinedIOInfo
    identifier_to_type: dict[str, ClassicalType | QubitType]
    found_input_ids: set[int]
    found_output_ids: set[int]
    qubit_builder: QubitIOInfoBuilder

    def __init__(self, io: CombinedIOInfo) -> None:
        """Construct the LeqoTransformer."""
        super().__init__()
        self.io = io
        self.identifier_to_type = {}
        self.found_input_ids = set()
        self.found_output_ids = set()
        self.qubit_builder = QubitIOInfoBuilder(io.qubit)

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

    def get_some_indentifier_from_alias(
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
                return self.get_some_indentifier_from_alias(value.lhs)
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
        input, dirty = self.get_declaration_annotation_info(
            name,
            node.annotations,
        )
        self.update_input_id(input)
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
            self.get_some_indentifier_from_alias(node.value).name
        ]
        self.identifier_to_type[name] = found_type

        match found_type:
            case QubitType():
                self.qubit_builder.handle_alias(node, output_id, reusable)
            case BitType():
                pass
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
        return node

from __future__ import annotations

from io import UnsupportedOperation
from itertools import chain

from openqasm3.ast import (
    AliasStatement,
    Annotation,
    Concatenation,
    Expression,
    Identifier,
    IndexExpression,
    Program,
    QASMNode,
    QubitDeclaration,
)

from app.openqasm3.visitor import LeqoTransformer
from app.processing.graph import (
    IOInfo,
    QubitAnnotationInfo,
    QubitInputInfo,
    QubitOutputInfo,
)
from app.processing.utils import expr_to_int, parse_io_annotation, parse_qasm_index


class ParseAnnotationsVisitor(LeqoTransformer[None]):
    """Parse input/output qubits of a single qasm-snippet.

    Do it the following way:
    - give every declared qubit (not qubit-reg) and id, based on declaration order
    - create map that points from declared identifiers to ids, this also parses aliases
    - store annotation info based on the id of the qubit
    """

    qubit_id: int
    alias_to_ids: dict[str, list[int]]
    found_input_ids: set[int]
    found_output_ids: set[int]
    io: IOInfo

    def __init__(self, io: IOInfo) -> None:
        """Construct the LeqoTransformer.

        :param io: The IOInfo to be modified in-place.
        """
        super().__init__()
        self.io = io
        self.qubit_id = 0
        self.alias_to_ids = {}
        self.found_input_ids = set()
        self.found_output_ids = set()

    def identifier_to_ids(self, identifier: str) -> list[int] | None:
        """Get ids via declaration_to_ids or alias_to_ids."""
        result = self.io.declaration_to_ids.get(identifier)
        return self.alias_to_ids.get(identifier) if result is None else result

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
        return (input_id, dirty)

    def visit_QubitDeclaration(self, node: QubitDeclaration) -> QASMNode:
        """Parse qubit-declarations and their corresponding input annotations."""
        name = node.qubit.name
        reg_size = expr_to_int(node.size) if node.size is not None else 1
        input_id, dirty = self.get_declaration_annotation_info(name, node.annotations)

        qubit_ids = []
        for i in range(reg_size):
            qubit_ids.append(self.qubit_id)
            input_info = QubitInputInfo(input_id, i) if input_id is not None else None
            self.io.id_to_info[self.qubit_id] = QubitAnnotationInfo(
                input=input_info,
                dirty=dirty,
            )
            self.qubit_id += 1
        self.io.declaration_to_ids[name] = qubit_ids

        if input_id is not None:
            self.io.input_to_ids[input_id] = qubit_ids
            if input_id in self.found_input_ids:
                msg = f"Unsupported: duplicate input id: {input_id}"
                raise IndexError(msg)
            self.found_input_ids.add(input_id)
        elif dirty:
            self.io.dirty_ancillas.extend(qubit_ids)
        else:  # non-input and non-dirty
            self.io.required_ancillas.extend(qubit_ids)

        return self.generic_visit(node)

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

    def visit_AliasStatement(self, node: AliasStatement) -> QASMNode:
        """Parse qubit-alias and their corresponding output annotations."""
        name = node.target.name

        qubit_ids = self.alias_expr_to_ids(node.value)
        match qubit_ids:
            case None:  # non-qubit in alias expression (classic)
                return self.generic_visit(node)
            case []:
                msg = f"Failed to parse alias statement {node}"
                raise RuntimeError(msg)

        output_id, reusable = self.get_alias_annotation_info(name, node.annotations)
        if output_id is not None:
            if output_id in self.found_output_ids:
                msg = f"Unsupported: duplicate output id: {output_id}"
                raise IndexError(msg)
            self.found_output_ids.add(output_id)

        self.alias_to_ids[name] = qubit_ids
        if output_id is not None:
            self.io.output_to_ids[output_id] = qubit_ids
        elif reusable:
            self.io.reusable_ancillas.extend(qubit_ids)

        for i, id in enumerate(qubit_ids):
            current_info = self.io.id_to_info[id]
            if reusable:
                if current_info.output is not None:
                    msg = f"alias {name} declares output qubit as reusable"
                    raise UnsupportedOperation(msg)
                current_info.reusable = True
            elif output_id is not None:
                if current_info.output is not None:
                    msg = f"alias {name} tries to overwrite already declared output"
                    raise UnsupportedOperation(msg)
                if current_info.reusable:
                    msg = f"alias {name} declares output for reusable qubit"
                    raise UnsupportedOperation(msg)
                current_info.output = QubitOutputInfo(output_id, i)
        return self.generic_visit(node)

    @staticmethod
    def raise_on_non_contiguous_range(numbers: set[int], name_of_check: str) -> None:
        """Check if int set is contiguous."""
        for i, j in enumerate(sorted(numbers)):
            if i == j:
                continue
            msg = f"Unsupported: Missing {name_of_check} index {i}, next index was {j}"
            raise IndexError(msg)

    def visit_Program(self, node: Program) -> QASMNode:
        """Ensure contiguous input/output indexes."""
        result = self.generic_visit(node)
        self.raise_on_non_contiguous_range(self.found_input_ids, "input")
        self.raise_on_non_contiguous_range(self.found_output_ids, "output")

        returned_dirty = set(self.io.id_to_info.keys())
        returned_dirty.difference_update(
            self.io.reusable_ancillas,
            self.io.reusable_after_uncompute,
            set(chain(*self.io.output_to_ids.values())),
        )
        self.io.returned_dirty_ancillas = sorted(returned_dirty)

        return result

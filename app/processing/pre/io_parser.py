from __future__ import annotations

from io import UnsupportedOperation

from openqasm3.ast import (
    AliasStatement,
    Annotation,
    Concatenation,
    Expression,
    Identifier,
    IndexExpression,
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


class IOParse(LeqoTransformer[None]):
    """Parse input/output qubits of a single qasm-snippet.

    Do it the following way:
    - give every declared qubit (not qubit-reg) and id, based on declaration order
    - create map that points from declared identifiers to ids, this also parses aliases
    - store annotation info based on the id of the qubit
    """

    qubit_id: int
    input_counter: int
    output_counter: int
    io: IOInfo

    def __init__(self, io: IOInfo) -> None:
        """Construct the LeqoTransformer.

        :param io: The IOInfo to be modified in place.
        """
        super().__init__()
        self.qubit_id = 0
        self.input_counter = 0
        self.output_counter = 0
        self.io = io

    def visit_QubitDeclaration(self, node: QubitDeclaration) -> QASMNode:
        """Parse qubit-declarations and their corresponding input annotations."""
        name = node.qubit.name
        size = expr_to_int(node.size) if node.size is not None else 1
        input_id: int | None = None
        dirty = False
        for annotation in node.annotations:
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
                    dirty = True
                case "leqo.output" | "leqo.reusable":
                    msg = f"Unsupported: {annotation.keyword} annotations over QubitDeclaration {name}"
                    raise UnsupportedOperation(msg)
        if input_id is not None and dirty:
            msg = (
                f"Unsupported: dirty and input annotations over QubitDeclaration {name}"
            )
            raise UnsupportedOperation(msg)

        qubit_ids = []
        for i in range(size):
            qubit_ids.append(self.qubit_id)
            input_info = QubitInputInfo(input_id, i) if input_id is not None else None
            self.io.id_to_info[self.qubit_id] = QubitAnnotationInfo(
                input=input_info,
                dirty=dirty,
            )
            self.qubit_id += 1

        if input_id is not None:
            if input_id == self.input_counter:
                self.input_counter += 1
            else:
                msg = f"expected input index {self.input_counter} but got {input_id}"
                raise IndexError(msg)
            self.io.input_to_ids[input_id] = qubit_ids
        self.io.declaration_to_id[name] = qubit_ids
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
    ) -> list[int]:
        """Recursively get IDs list for alias expression."""
        match value:
            case IndexExpression():
                collection = value.collection
                if not isinstance(collection, Identifier):
                    msg = f"Unsupported expression in alias: {type(collection)}"
                    raise TypeError(msg)
                source = self.io.identifier_to_ids(collection.name)
                indices = parse_qasm_index([value.index], len(source))
                return [source[i] for i in indices]
            case Identifier():
                return self.io.identifier_to_ids(value.name)
            case Concatenation():
                return self.alias_expr_to_ids(value.lhs) + self.alias_expr_to_ids(
                    value.rhs,
                )
            case Expression():
                msg = f"Unsupported expression in alias: {type(value)}"
                raise UnsupportedOperation(msg)
            case _:
                msg = f"{type(value)} is not implemented as alias expression"
                raise NotImplementedError(msg)

    def visit_AliasStatement(self, node: AliasStatement) -> QASMNode:
        """Parse qubit-alias and their corresponding output annotations."""
        name = node.target.name
        try:
            ids = self.alias_expr_to_ids(node.value)
        except KeyError:  # non-qubit in alias expression (classic)
            return self.generic_visit(node)
        output_id, reusable = self.get_alias_annotation_info(name, node.annotations)

        if output_id is not None:
            if output_id == self.output_counter:
                self.output_counter += 1
            else:
                msg = f"expected output index {self.output_counter} but got {output_id}"
                raise IndexError(msg)

        if len(ids) == 0:
            msg = f"Failed to parse alias statement {node}"
            raise RuntimeError(msg)
        self.io.alias_to_id[name] = ids
        if output_id is not None:
            self.io.output_to_ids[output_id] = ids
        for i, id in enumerate(ids):
            if reusable:
                if self.io.id_to_info[id].output is not None:
                    msg = f"alias {name} declares output qubit as reusable"
                    raise UnsupportedOperation(msg)
                self.io.id_to_info[id].reusable = True
            elif output_id is not None:
                if self.io.id_to_info[id].output is not None:
                    msg = f"alias {name} tries to overwrite already declared output"
                    raise UnsupportedOperation(msg)
                if self.io.id_to_info[id].reusable:
                    msg = f"alias {name} declares output for reusable qubit"
                    raise UnsupportedOperation(msg)
                self.io.id_to_info[id].output = QubitOutputInfo(output_id, i)
        return self.generic_visit(node)

from __future__ import annotations

from copy import copy
from io import UnsupportedOperation
from itertools import chain

from openqasm3.ast import (
    AliasStatement,
    Annotation,
    BitType,
    BoolType,
    ClassicalDeclaration,
    Concatenation,
    Expression,
    FloatType,
    Identifier,
    IndexExpression,
    IntType,
    Program,
    QASMNode,
    QubitDeclaration,
)

from app.openqasm3.visitor import LeqoTransformer
from app.processing.graph import (
    ClassicalIOInstance,
    IOInfo,
    QubitIOInstance,
)
from app.processing.utils import expr_to_int, parse_io_annotation, parse_qasm_index


class ParseAnnotationsVisitor(LeqoTransformer[None]):
    __next_qubit_id: int
    __name_to_info: dict[str, QubitIOInstance | ClassicalIOInstance]
    __found_input_ids: set[int]
    __found_output_ids: set[int]
    io: IOInfo

    def __init__(self, io: IOInfo) -> None:
        """Construct the LeqoTransformer.

        :param io: The IOInfo to be modified in-place.
        """
        super().__init__()
        self.io = io
        self.__next_qubit_id = 0
        self.__name_to_info = {}
        self.__found_input_ids = set()
        self.__found_output_ids = set()

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

    def __alias_expr_to_new_info(
        self,
        name: str,
        value: Identifier | IndexExpression | Concatenation | Expression,
    ) -> QubitIOInstance | ClassicalIOInstance | None:
        match value:
            case IndexExpression():
                collection = value.collection
                if not isinstance(collection, Identifier):
                    msg = f"Unsupported expression in alias: {type(collection)}"
                    raise TypeError(msg)
                source = self.__name_to_info.get(collection.name)
                match source:
                    case None:
                        return None
                    case QubitIOInstance():
                        qubit_ids = source.ids
                        indices = parse_qasm_index([value.index], len(qubit_ids))
                        return QubitIOInstance(name, [source.ids[i] for i in indices])
                    case ClassicalIOInstance():
                        if source.type == BitType:
                            return ClassicalIOInstance(
                                name,
                                BitType,
                                len(
                                    parse_qasm_index([value.index], source.size),
                                ),
                            )
                        return copy(source)
            case Identifier():
                info = copy(self.__name_to_info.get(value.name))
                if info is not None:
                    info.name = name
                return info
            case Concatenation():
                lhs = self.__alias_expr_to_new_info(name, value.lhs)
                rhs = self.__alias_expr_to_new_info(name, value.rhs)
                match lhs, rhs:
                    case QubitIOInstance(ids=li), QubitIOInstance(ids=ri):
                        return QubitIOInstance(name, li + ri)
                    case ClassicalIOInstance(), ClassicalIOInstance():
                        if lhs.type == rhs.type == BitType:
                            return ClassicalIOInstance(
                                name,
                                BitType,
                                lhs.size + rhs.size,
                            )
                return None
            case Expression():
                msg = f"Unsupported expression in alias: {type(value)}"
                raise UnsupportedOperation(msg)
            case _:
                msg = f"{type(value)} is not implemented as alias expression"
                raise NotImplementedError(msg)

    def visit_QubitDeclaration(self, node: QubitDeclaration) -> QASMNode:
        """Parse qubit-declarations and their corresponding input annotations."""
        name = node.qubit.name
        reg_size = expr_to_int(node.size) if node.size is not None else 1
        input_id, dirty = self.get_declaration_annotation_info(name, node.annotations)

        qubit_ids = []
        for _ in range(reg_size):
            qubit_ids.append(self.__next_qubit_id)
            self.__next_qubit_id += 1
        self.io.qubits.declaration_to_ids[name] = qubit_ids

        info = QubitIOInstance(name, qubit_ids)
        self.__name_to_info[name] = info
        if input_id is not None:
            self.io.inputs[input_id] = info
            if input_id in self.__found_input_ids:
                msg = f"Unsupported: duplicate input id: {input_id}"
                raise IndexError(msg)
            self.__found_input_ids.add(input_id)
        elif dirty:
            self.io.qubits.required_dirty_ids.extend(qubit_ids)
        else:  # non-input and non-dirty
            self.io.qubits.required_reusable_ids.extend(qubit_ids)

        return self.generic_visit(node)

    def visit_ClassicalDeclaration(self, node: ClassicalDeclaration) -> QASMNode:
        name = node.identifier.name
        input_id, dirty = self.get_declaration_annotation_info(name, node.annotations)

        if dirty:
            msg = f"""Unsupported: dirty annotation over classical {name}"""
            raise UnsupportedOperation(msg)

        match node.type:
            case BitType():
                size = 1 if node.type.size is None else expr_to_int(node.type.size)
            case IntType():
                size = 32 if node.type.size is None else expr_to_int(node.type.size)
            case FloatType():
                size = 32 if node.type.size is None else expr_to_int(node.type.size)
            case BoolType():
                size = 1
            case _:
                return self.generic_visit(node)

        info = ClassicalIOInstance(name, type(node.type), size)
        self.__name_to_info[name] = info
        if input_id is not None:
            self.io.inputs[input_id] = info
            if input_id in self.__found_input_ids:
                msg = f"Unsupported: duplicate input id: {input_id}"
                raise IndexError(msg)
            self.__found_input_ids.add(input_id)

        return self.generic_visit(node)

    def visit_AliasStatement(self, node: AliasStatement) -> QASMNode:
        """Parse qubit-alias and their corresponding output annotations."""
        name = node.target.name
        info = self.__alias_expr_to_new_info(name, node.value)

        output_id, reusable = self.get_alias_annotation_info(name, node.annotations)
        if output_id is not None:
            if output_id in self.__found_output_ids:
                msg = f"Unsupported: duplicate output id: {output_id}"
                raise IndexError(msg)
            self.__found_output_ids.add(output_id)

        self.__name_to_info[name] = info
        if output_id is not None:
            self.io.outputs[output_id] = info
        elif reusable:
            if isinstance(info, ClassicalIOInstance):
                msg = f"Unsupported: reusable annotation over classical {info.name}"
                raise UnsupportedOperation(msg)
            self.io.qubits.returned_reusable_ids.extend(info.ids)

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
        self.raise_on_non_contiguous_range(self.__found_input_ids, "input")
        self.raise_on_non_contiguous_range(self.__found_output_ids, "output")

        returned_dirty = set(chain(*self.io.qubits.declaration_to_ids.values()))
        for qubit_id in self.io.qubits.returned_reusable_ids:
            try:
                returned_dirty.remove(qubit_id)
            except KeyError:
                msg = f"Unsupported: qubit with {qubit_id} was parsed as reusable twice"
                raise UnsupportedOperation(msg) from None
        for qubit_id in self.io.qubits.returned_reusable_after_uncompute_ids:
            try:
                returned_dirty.remove(qubit_id)
            except KeyError:
                msg = f"Unsupported: qubit with {qubit_id} was parsed as reusable and as reusable_after_uncompute"
                raise UnsupportedOperation(msg) from None
        for output in self.io.outputs.values():
            if isinstance(output, QubitIOInstance):
                for qubit_id in output.ids:
                    try:
                        returned_dirty.remove(qubit_id)
                    except KeyError:
                        msg = f"Unsupported: qubit with {qubit_id} was parsed as reusable and output"
                        raise UnsupportedOperation(msg) from None
        self.io.qubits.returned_dirty_ids = sorted(returned_dirty)

        return result

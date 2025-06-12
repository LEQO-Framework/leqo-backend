"""Parse input/output info for single code snippet over leqo-annotations."""

from __future__ import annotations

from copy import deepcopy
from itertools import chain

from openqasm3.ast import (
    AliasStatement,
    Annotation,
    BitType,
    BooleanLiteral,
    BoolType,
    BranchingStatement,
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

from app.exceptions import InternalServerError, InvalidInputError
from app.model.data_types import (
    DEFAULT_FLOAT_SIZE,
    DEFAULT_INT_SIZE,
    LeqoSupportedType,
)
from app.model.data_types import (
    BitType as LeqoBitType,
)
from app.model.data_types import (
    BoolType as LeqoBoolType,
)
from app.model.data_types import (
    FloatType as LeqoFloatType,
)
from app.model.data_types import (
    IntType as LeqoIntType,
)
from app.openqasm3.visitor import LeqoTransformer
from app.processing.graph import (
    ClassicalIOInstance,
    IOInfo,
    QubitInfo,
    QubitIOInstance,
)
from app.processing.utils import expr_to_int, parse_io_annotation, parse_qasm_index
from app.utils import not_none_or, opt_call


class ParseAnnotationsVisitor(LeqoTransformer[None]):
    """Non-modifying visitor to parse io info."""

    __next_qubit_id: int
    __name_to_info: dict[str, QubitIOInstance | ClassicalIOInstance]
    __found_input_ids: set[int]
    __found_output_ids: set[int]
    __in_uncompute: bool
    __node_id: str | None
    io: IOInfo
    qubit: QubitInfo

    def __init__(
        self, io: IOInfo, qubit: QubitInfo, node_id: str | None = None
    ) -> None:
        """Construct the ParseAnnotationsVisitor.

        :param io: The IOInfo to be modified in-place.
        :param qubit: The QubitInfo to be modified in-place.
        """
        super().__init__()
        self.io = io
        self.qubit = qubit
        self.__node_id = node_id
        self.__next_qubit_id = 0
        self.__name_to_info = {}
        self.__found_input_ids = set()
        self.__found_output_ids = set()
        self.__in_uncompute = False

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
                        raise InvalidInputError(msg, node=self.__node_id)
                    input_id = parse_io_annotation(annotation, self.__node_id)
                case "leqo.dirty":
                    if dirty:
                        msg = f"Unsupported: two dirty annotations over {name}"
                        raise InvalidInputError(msg, node=self.__node_id)
                    if (
                        annotation.command is not None
                        and annotation.command.strip() != ""
                    ):
                        msg = f"Unsupported: found {annotation.command} over dirty annotations {name}"
                        raise InvalidInputError(msg, node=self.__node_id)
                    dirty = True
                case "leqo.output" | "leqo.reusable" | "leqo.uncompute":
                    msg = f"Unsupported: {annotation.keyword} annotations over QubitDeclaration {name}"
                    raise InvalidInputError(msg, node=self.__node_id)
        if input_id is not None and dirty:
            msg = (
                f"Unsupported: dirty and input annotations over QubitDeclaration {name}"
            )
            raise InvalidInputError(msg, node=self.__node_id)
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
                        raise InvalidInputError(msg, node=self.__node_id)
                    output_id = parse_io_annotation(annotation, self.__node_id)
                case "leqo.reusable":
                    if reusable:
                        msg = f"Unsupported: two reusable annotations over {name}"
                        raise InvalidInputError(msg, node=self.__node_id)
                    if (
                        annotation.command is not None
                        and annotation.command.strip() != ""
                    ):
                        msg = f"Unsupported: found {annotation.command} over reusable annotations {name}"
                        raise InvalidInputError(msg, node=self.__node_id)
                    reusable = True
                case "leqo.input" | "leqo.dirty" | "leqo.uncompute":
                    msg = f"Unsupported: {annotation.keyword} annotations over AliasStatement {name}"
                    raise InvalidInputError(msg, node=self.__node_id)
        if output_id is not None and reusable:
            msg = f"Unsupported: input and dirty annotations over AliasStatement {name}"
            raise InvalidInputError(msg, node=self.__node_id)
        return (output_id, reusable)

    def get_branching_annotation_info(self, annotations: list[Annotation]) -> bool:
        """Extract annotation info for branching statement, throw error on bad usage."""
        uncompute = False
        for annotation in annotations:
            match annotation.keyword:
                case "leqo.uncompute":
                    if uncompute:
                        msg = "Unsupported: two uncompute annotations over if-then-else-block"
                        raise InvalidInputError(msg, node=self.__node_id)
                    if (
                        annotation.command is not None
                        and annotation.command.strip() != ""
                    ):
                        msg = f"Unsupported: found {annotation.command} over uncompute annotation over if-then-else-block"
                        raise InvalidInputError(msg, node=self.__node_id)
                    uncompute = True
                case "leqo.input" | "leqo.dirty" | "leqo.output" | "leqo.reusable":
                    msg = f"Unsupported: {annotation.keyword} annotations over BranchingStatement if-then-else-block"
                    raise InvalidInputError(msg, node=self.__node_id)
        return uncompute

    def __alias_expr_to_new_info(  # noqa: PLR0911, PLR0912
        self,
        name: str,
        value: Identifier | IndexExpression | Concatenation | Expression,
    ) -> QubitIOInstance | ClassicalIOInstance | None:
        """Recursively get new (Qubit/Classical)IOInstance from alias expression.

        :param name: New name to use in the info.
        :param value: The alias expression to parse.
        """
        match value:
            case IndexExpression():
                collection = value.collection
                if not isinstance(collection, Identifier):
                    return None
                source = self.__name_to_info.get(collection.name)
                match source:
                    case None:
                        return None
                    case QubitIOInstance():
                        qubit_ids = source.ids
                        if not isinstance(qubit_ids, list):
                            msg = "Unsupported: Can't Index single qubit (non reg)"
                            raise InvalidInputError(msg, node=self.__node_id)
                        indices = parse_qasm_index(
                            [value.index], len(qubit_ids), self.__node_id
                        )
                        return QubitIOInstance(
                            name,
                            [qubit_ids[i] for i in indices]
                            if isinstance(indices, list)
                            else qubit_ids[indices],
                        )
                    case ClassicalIOInstance():
                        if isinstance(source.type, LeqoBitType):
                            source_size = source.type.size
                            if source_size is None:
                                msg = "Unsupported: Can't Index single bit (non array)"
                                raise InvalidInputError(msg, node=self.__node_id)
                            result = parse_qasm_index(
                                [value.index], source_size, self.__node_id
                            )
                            return ClassicalIOInstance(
                                name,
                                LeqoBitType(
                                    len(result) if isinstance(result, list) else None
                                ),
                            )
                        msg = f"Unsupported: Can't handle indexed {source.type}"
                        raise InvalidInputError(msg, node=self.__node_id)
            case Identifier():
                info = deepcopy(self.__name_to_info.get(value.name))
                if info is not None:
                    info.name = name
                return info
            case Concatenation():
                lhs = self.__alias_expr_to_new_info(name, value.lhs)
                rhs = self.__alias_expr_to_new_info(name, value.rhs)
                match lhs, rhs:
                    case QubitIOInstance(ids=li), QubitIOInstance(ids=ri):
                        if not (isinstance(li, list) and isinstance(ri, list)):
                            msg = "Unsupported: Can't concatenate single qubits."
                            raise InvalidInputError(msg, node=self.__node_id)
                        return QubitIOInstance(name, li + ri)
                    case ClassicalIOInstance(), ClassicalIOInstance():
                        if (
                            isinstance(lhs.type, LeqoBitType)
                            and isinstance(rhs.type, LeqoBitType)
                            and lhs.type.size is not None
                            and rhs.type.size is not None
                        ):
                            return ClassicalIOInstance(
                                name, LeqoBitType(lhs.type.size + rhs.type.size)
                            )
                        msg = f"Unsupported: Can't concatenate non-bit-array types: {lhs.type} {rhs.type}"
                        raise InvalidInputError(msg, node=self.__node_id)
                return None
            case _:
                msg = f"{type(value)} is not implemented as alias expression"
                raise InternalServerError(msg, node=self.__node_id)

    def visit_QubitDeclaration(self, node: QubitDeclaration) -> QASMNode:
        """Parse qubit-declarations and their corresponding input/dirty annotations."""
        name = node.qubit.name
        reg_size = expr_to_int(node.size) if node.size is not None else None
        input_id, dirty = self.get_declaration_annotation_info(name, node.annotations)

        if reg_size is None:
            qubit_ids: int | list[int] = self.__next_qubit_id
            self.__next_qubit_id += 1
        else:
            qubit_ids = []
            for _ in range(reg_size):
                qubit_ids.append(self.__next_qubit_id)
                self.__next_qubit_id += 1
        self.qubit.declaration_to_ids[name] = (
            qubit_ids if isinstance(qubit_ids, list) else [qubit_ids]
        )

        info = QubitIOInstance(name, qubit_ids)
        self.__name_to_info[name] = info
        if input_id is not None:
            if input_id in self.__found_input_ids:
                msg = f"Unsupported: duplicate input id: {input_id}"
                raise IndexError(msg)
            self.__found_input_ids.add(input_id)
            self.io.inputs[input_id] = info
        elif dirty:
            if isinstance(qubit_ids, list):
                self.qubit.dirty_ids.extend(qubit_ids)
            else:
                self.qubit.dirty_ids.append(qubit_ids)
        elif isinstance(qubit_ids, list):
            self.qubit.clean_ids.extend(qubit_ids)
        else:
            self.qubit.clean_ids.append(qubit_ids)

        return self.generic_visit(node)

    def visit_ClassicalDeclaration(self, node: ClassicalDeclaration) -> QASMNode:
        """Parse classical-declarations and their corresponding input annotations."""
        name = node.identifier.name
        input_id, dirty = self.get_declaration_annotation_info(name, node.annotations)

        if dirty:
            msg = f"""Unsupported: dirty annotation over classical {name}"""
            raise InvalidInputError(msg, node=self.__node_id)

        leqo_type: LeqoSupportedType
        match node.type:
            case BitType():
                leqo_type = LeqoBitType(opt_call(expr_to_int, node.type.size))
            case IntType():
                leqo_type = LeqoIntType(
                    not_none_or(opt_call(expr_to_int, node.type.size), DEFAULT_INT_SIZE)
                )
            case FloatType():
                leqo_type = LeqoFloatType(
                    not_none_or(
                        opt_call(expr_to_int, node.type.size), DEFAULT_FLOAT_SIZE
                    )
                )
            case BoolType():
                leqo_type = LeqoBoolType()
            case _:
                return self.generic_visit(node)

        info = ClassicalIOInstance(name, leqo_type)
        self.__name_to_info[name] = info
        if input_id is not None:
            if input_id in self.__found_input_ids:
                msg = f"Unsupported: duplicate input id: {input_id}"
                raise IndexError(msg)
            if self.__in_uncompute:
                msg = f"Unsupported: input declaration over {info.name} in uncompute block"
                raise InvalidInputError(msg, node=self.__node_id)
            self.__found_input_ids.add(input_id)
            self.io.inputs[input_id] = info

        return self.generic_visit(node)

    def visit_AliasStatement(self, node: AliasStatement) -> QASMNode:
        """Parse alias and their corresponding output/reusalbe annotations."""
        name = node.target.name
        info = self.__alias_expr_to_new_info(name, node.value)
        if info is None:
            return self.generic_visit(node)

        output_id, reusable = self.get_alias_annotation_info(name, node.annotations)
        if output_id is not None:
            if output_id in self.__found_output_ids:
                msg = f"Unsupported: duplicate output id: {output_id}"
                raise IndexError(msg)
            self.__found_output_ids.add(output_id)

        self.__name_to_info[name] = info
        if output_id is not None:
            if self.__in_uncompute:
                msg = f"Unsupported: output declaration over {info.name} in uncompute block"
                raise InvalidInputError(msg, node=self.__node_id)
            self.io.outputs[output_id] = info
        elif reusable:
            if isinstance(info, ClassicalIOInstance):
                msg = f"Unsupported: reusable annotation over classical {info.name}"
                raise InvalidInputError(msg, node=self.__node_id)
            if self.__in_uncompute:
                if isinstance(info.ids, list):
                    self.qubit.uncomputable_ids.extend(info.ids)
                else:
                    self.qubit.uncomputable_ids.append(info.ids)
            elif isinstance(info.ids, list):
                self.qubit.reusable_ids.extend(info.ids)
            else:
                self.qubit.reusable_ids.append(info.ids)

        return self.generic_visit(node)

    def visit_BranchingStatement(self, node: BranchingStatement) -> QASMNode:
        """Parse if-then-else-block and their corresponding uncompute annotations."""
        uncompute = self.get_branching_annotation_info(node.annotations)
        if not uncompute:
            return self.generic_visit(node)
        if self.__in_uncompute:
            msg = "Unsupported: nested uncompute blocks"
            raise InvalidInputError(msg, node=self.__node_id)
        if not isinstance(node.condition, BooleanLiteral) or node.condition.value:
            msg = f"Unsupported: invalid expression in uncompute-annotated if-then-else-block: {node.condition}"
            raise InvalidInputError(msg, node=self.__node_id)
        if len(node.else_block) > 0:
            msg = "Unsupported: uncompute-annotated if-then-else-block has else-block"
            raise InvalidInputError(msg, node=self.__node_id)
        self.__in_uncompute = True
        result = self.generic_visit(node)
        self.__in_uncompute = False
        return result

    @staticmethod
    def raise_on_non_contiguous_range(numbers: set[int], name_of_check: str) -> None:
        """Check if int-set is contiguous and starting from 0."""
        for i, j in enumerate(sorted(numbers)):
            if i == j:
                continue
            msg = f"Unsupported: Missing {name_of_check} index {i}, next index was {j}"
            raise IndexError(msg)

    def visit_Program(self, node: Program) -> QASMNode:
        """Ensure contiguous input/output indexes and compute returned-dirty qubits."""
        result = self.generic_visit(node)

        self.raise_on_non_contiguous_range(self.__found_input_ids, "input")
        self.raise_on_non_contiguous_range(self.__found_output_ids, "output")

        returned_dirty = set(chain(*self.qubit.declaration_to_ids.values()))
        for qubit_id in self.qubit.reusable_ids:
            try:
                returned_dirty.remove(qubit_id)
            except KeyError:
                msg = f"Unsupported: qubit with {qubit_id} was parsed as reusable twice"
                raise InvalidInputError(msg, node=self.__node_id)
        for qubit_id in self.qubit.uncomputable_ids:
            try:
                returned_dirty.remove(qubit_id)
            except KeyError:
                msg = f"Unsupported: qubit with {qubit_id} was parsed as reusable (in uncompute) twice"
                raise InvalidInputError(msg, node=self.__node_id)
        for output in self.io.outputs.values():
            if isinstance(output, QubitIOInstance):
                output_ids = (
                    output.ids if isinstance(output.ids, list) else [output.ids]
                )
                for qubit_id in output_ids:
                    try:
                        returned_dirty.remove(qubit_id)
                    except KeyError:
                        msg = f"Unsupported: qubit with {qubit_id} was parsed as reusable or output twice"
                        raise InvalidInputError(msg, node=self.__node_id)
        self.qubit.entangled_ids = sorted(returned_dirty)

        return result

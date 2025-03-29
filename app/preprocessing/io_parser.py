from io import UnsupportedOperation

from openqasm3.ast import (
    AliasStatement,
    Annotation,
    Concatenation,
    Expression,
    Identifier,
    IndexElement,
    IndexExpression,
    Program,
    QASMNode,
    QubitDeclaration,
)
from openqasm3.visitor import QASMTransformer

from app.lib.ast_utils import expr_to_int, parse_io_annotation, parse_qasm_index
from app.model.dataclass import (
    SingleInputInfo,
    SingleIOInfo,
    SingleOutputInfo,
    SnippetIOInfo,
)


class IOParse(QASMTransformer[SnippetIOInfo]):
    qubit_id: int = 0

    def extract_io_info(self, program: Program) -> SnippetIOInfo:
        result = SnippetIOInfo()
        self.visit(program, result)
        return result

    def visit_QubitDeclaration(
        self,
        node: QubitDeclaration,
        context: SnippetIOInfo,
    ) -> QASMNode:
        name = node.qubit.name
        size = expr_to_int(node.size)
        input_id: int | None = None
        for annotation in node.annotations:
            if annotation.keyword == "leqo.input":
                if input_id is not None:
                    msg = f"Unsuported: two input annotations over {name}"
                    raise UnsupportedOperation(msg)
                input_id = parse_io_annotation(annotation)
            elif annotation.keyword in ("leqo.output", "leqo.reusable"):
                msg = f"Unsuported: output/reusable annotations over QubitDeclaration {name}"
                raise UnsupportedOperation(msg)
        context.declaration_to_id[name] = []
        for i in range(size):
            context.declaration_to_id[name].append(self.qubit_id)
            input_info = SingleInputInfo(input_id, i) if input_id is not None else None
            context.id_to_info[self.qubit_id] = SingleIOInfo(input=input_info)
            self.qubit_id += 1
        return self.generic_visit(node, context)

    def get_alias_annotation_info(
        self,
        name: str,
        annotations: list[Annotation],
    ) -> tuple[int | None, bool]:
        output_id: int | None = None
        reusable = False
        for annotation in annotations:
            if annotation.keyword == "leqo.output":
                if output_id is not None or reusable:
                    msg = f"Unsuported: two output/reusable annotations over {name}"
                    raise UnsupportedOperation(msg)
                output_id = parse_io_annotation(annotation)
            elif annotation.keyword == "leqo.reusable":
                if output_id is not None or reusable:
                    msg = f"Unsuported: two output/reusable annotations over {name}"
                    raise UnsupportedOperation(msg)
                reusable = True
            elif annotation.keyword == "leqo.input":
                msg = f"Unsuported: input annotations over AliasStatement {name}"
                raise UnsupportedOperation(msg)
        return (output_id, reusable)

    def get_indexed_expr_to_ids(
        self,
        source_name: str,
        index: IndexElement,
        context: SnippetIOInfo,
    ) -> list[int]:
        source = context.identifier_to_ids(source_name)
        indices = parse_qasm_index([index], len(source))
        return [source[i] for i in indices]

    def alias_expr_to_ids(
        self,
        value: Identifier | IndexExpression | Concatenation | Expression,
        context: SnippetIOInfo,
    ) -> list[int]:
        match value:
            case IndexExpression():
                collection = value.collection
                if not isinstance(collection, Identifier):
                    msg = f"Unsupported expresion in alias: {type(collection)}"
                    raise TypeError(msg)
                return self.get_indexed_expr_to_ids(
                    collection.name,
                    value.index,
                    context,
                )
            case Identifier():
                return context.identifier_to_ids(value.name)
            case Concatenation():
                return self.alias_expr_to_ids(
                    value.lhs,
                    context,
                ) + self.alias_expr_to_ids(value.rhs, context)
            case Expression():
                msg = f"Unsupported expresion in alias: {type(value)}"
                raise UnsupportedOperation(msg)
            case _:
                msg = f"{type(value)} is not implemented as alias expresion"
                raise NotImplementedError(msg)

    def visit_AliasStatement(
        self,
        node: AliasStatement,
        context: SnippetIOInfo,
    ) -> QASMNode:
        name = node.target.name
        ids = self.alias_expr_to_ids(node.value, context)
        output_id, reusable = self.get_alias_annotation_info(name, node.annotations)

        if ids is None:
            msg = f"Failed to parse alias statement {node}"
            raise UnsupportedOperation(msg)
        context.alias_to_id[name] = ids
        for i, id in enumerate(ids):
            if reusable:
                if context.id_to_info[id].output is not None:
                    msg = f"alias {name} declares output qubit as reusable"
                    raise UnsupportedOperation(msg)
                context.id_to_info[id].reusable = True
            elif output_id is not None:
                if context.id_to_info[id].output is not None:
                    msg = f"alias {name} tries to overwrite already declared output"
                    raise UnsupportedOperation(msg)
                if context.id_to_info[id].reusable:
                    msg = f"alias {name} declares output for reusable qubit"
                    raise UnsupportedOperation(msg)
                context.id_to_info[id].output = SingleOutputInfo(output_id, i)
        return self.generic_visit(node, context)

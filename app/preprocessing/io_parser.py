from io import UnsupportedOperation

from openqasm3.ast import (
    AliasStatement,
    Identifier,
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
        self.qubit_id += size
        return self.generic_visit(node, context)

    def visit_AliasStatement(
        self,
        node: AliasStatement,
        context: SnippetIOInfo,
    ) -> QASMNode:
        name = node.target.name
        output_id: int | None = None
        reusable = False
        for annotation in node.annotations:
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
        value = node.value
        ids: list[int] | None = None
        match value:
            case IndexExpression():
                collection_name = value.collection.name
                collection = context.identifier_to_ids(collection_name)
                indices = parse_qasm_index([value.index], len(collection))
                ids = [collection[i] for i in indices]
            case Identifier():
                ids = context.identifier_to_ids(value.name)
            case _:
                msg = f"{type(value)} is not implemented as alias expresion"
                raise NotImplementedError(msg)

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

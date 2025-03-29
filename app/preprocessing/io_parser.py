from io import UnsupportedOperation

from openqasm3.ast import Program, QASMNode, QubitDeclaration
from openqasm3.visitor import QASMTransformer

from app.lib.ast_utils import expr_to_int, parse_io_annotation
from app.model.dataclass import SingleInputInfo, SingleIOInfo, SnippetIOInfo


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
            if input_id is not None:
                context.id_to_info[self.qubit_id] = SingleIOInfo(
                    input=SingleInputInfo(input_id, i),
                )
            self.qubit_id += 1
        self.qubit_id += size
        return self.generic_visit(node, context)

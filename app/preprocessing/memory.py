from openqasm3.ast import (
    QubitDeclaration,
)
from openqasm3.visitor import QASMTransformer

from app.model.SectionInfo import QasmDataType, SectionGlobal, SectionInfo


class MemoryTransformer(QASMTransformer[SectionInfo]):
    def visit_QubitDeclaration(
        self, node: QubitDeclaration, context: SectionInfo
    ) -> QubitDeclaration:
        input_annotations = [x for x in node.annotations if x.keyword == "leqo.input"]
        input_index: int | None = None
        match len(input_annotations):
            case 1:
                input_index = int(input_annotations[0].command)

            case count if count > 1:
                raise Exception("Only a single input is allowed")

        output_annotations = [x for x in node.annotations if x.keyword == "leqo.output"]
        output_index: int | None = None
        match len(output_annotations):
            case 1:
                output_index = int(output_annotations[0].command)

            case count if count > 1:
                raise Exception("Only a single output is allowed")

        context.globals[node.qubit.name] = SectionGlobal(
            QasmDataType.QUBIT,
            input_index,
            output_index,
        )
        return node

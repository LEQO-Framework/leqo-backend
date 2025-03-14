from openqasm3.ast import (
    QubitDeclaration,
)
from openqasm3.visitor import QASMTransformer

from app.model.SectionInfo import QasmDataType, SectionGlobal, SectionInfo
from app.preprocessing.utils import parse_io_range


class MemoryTransformer(QASMTransformer[SectionInfo]):
    def visit_QubitDeclaration(
        self, node: QubitDeclaration, context: SectionInfo
    ) -> QubitDeclaration:
        input_annotations = [x for x in node.annotations if x.keyword == "leqo.input"]
        input_index: int | None = None
        match len(input_annotations):
            case 1:
                input_index = parse_io_range(input_annotations[0].command)

            case count if count > 1:
                raise Exception("Only a single input is allowed")

        output_annotations = [x for x in node.annotations if x.keyword == "leqo.output"]
        output_index: int | None = None
        match len(output_annotations):
            case 1:
                output_index = parse_io_range(output_annotations[0].command)

            case count if count > 1:
                raise Exception("Only a single output is allowed")

        context.globals[node.qubit.name] = SectionGlobal(
            QasmDataType.QUBIT,
            input_index,
            output_index,
        )
        return node

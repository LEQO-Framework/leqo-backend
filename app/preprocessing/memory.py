from openqasm3.ast import (
    Identifier,
    IndexedIdentifier,
    QuantumReset,
    QubitDeclaration,
)
from openqasm3.visitor import QASMTransformer

from app.model.SectionInfo import QasmDataType, SectionGlobal, SectionInfo


class MemoryTransformer(QASMTransformer[SectionInfo]):
    def visit_QubitDeclaration(
        self, node: QubitDeclaration, context: SectionInfo
    ) -> QubitDeclaration:
        is_input = any(x for x in node.annotations if x.keyword == "leqo.input")
        is_output = any(x for x in node.annotations if x.keyword == "leqo.output")

        context.globals[node.qubit.name] = SectionGlobal(
            QasmDataType.QUBIT, is_input, is_output, isReset=False
        )
        return node

    def visit_QuantumReset(
        self, node: QuantumReset, context: SectionInfo
    ) -> QuantumReset:
        match node.qubits:
            case IndexedIdentifier():
                raise Exception("Not implemented")

            case Identifier():
                section_global = context.globals.get(node.qubits.name)
                if section_global is None:
                    raise Exception("Could not find section global")

                section_global.isReset = True

        return node

    def visit_Identifier(self, node: Identifier, context: SectionInfo) -> Identifier:
        section_global = context.globals.get(node.name)
        if section_global is not None:
            section_global.isReset = False

        return node

from openqasm3.ast import Program
from openqasm3.visitor import QASMTransformer

from app.model.dataclass import IOInfo


class IOParse(QASMTransformer[IOInfo]):
    def extract_io_info(self, program: Program) -> IOInfo:
        result = IOInfo()
        self.visit(program, result)
        return result

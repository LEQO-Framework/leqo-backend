from io import TextIOBase

from openqasm3.printer import Printer, PrinterState

from app.openqasm3.ast import CommentStatement


class LeqoPrinter(Printer):
    """
    QASMNode visitor that allows to print qasm programs including custom nodes.
    """

    def __init__(self, stream: TextIOBase):
        super().__init__(stream, chain_else_if=False)

    def visit_CommentStatement(self, node: CommentStatement, ctx: PrinterState) -> None:
        self._write_statement(f"/* {node.comment} */", ctx)

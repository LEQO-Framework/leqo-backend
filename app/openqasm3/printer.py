"""
Extended printing with support for custom comment nodes.
"""

from io import StringIO, TextIOBase

from openqasm3.ast import QASMNode
from openqasm3.printer import Printer, PrinterState

from app.openqasm3.ast import CommentStatement


def leqo_dumps(program: QASMNode) -> str:
    """
    Prints the given program as a string.

    :param program: The program to print
    :return: The program as a string
    """

    result = StringIO()
    LeqoPrinter(result).visit(program)
    return result.getvalue()


class LeqoPrinter(Printer):
    """
    QASMNode visitor that allows to print qasm programs including custom nodes.
    """

    def __init__(self, stream: TextIOBase):
        super().__init__(stream, chain_else_if=False)

    def visit_CommentStatement(self, node: CommentStatement, ctx: PrinterState) -> None:
        self._start_line(ctx)
        self.stream.write(f"/* {node.comment} */")
        self._end_line(ctx)

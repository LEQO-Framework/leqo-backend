from dataclasses import dataclass
from io import StringIO, TextIOBase

from openqasm3.ast import Include, Program, Statement
from openqasm3.printer import Printer, PrinterState


@dataclass
class CommentStatement(Statement):
    """
    Simple qasm statement representing a block comment.

    Output: `/* {comment} */`
    """

    comment: str


class ExtendedPrinter(Printer):
    """
    QASMNode visitor that allows to print qasm programs including custom nodes.
    """

    def __init__(self, stream: TextIOBase):
        super().__init__(stream, chain_else_if=False)

    def visit_CommentStatement(self, node: CommentStatement, ctx: PrinterState) -> None:
        self._write_statement(f"/* {node.comment} */", ctx)


class QASMBuilder:
    """
    Utility class to build QASM programs.
    """

    def __init__(self) -> None:
        self.includes: set[str] = set()
        self.statements: list[Statement] = []

    def include(self, filename: str) -> None:
        """
        Prepends a `#include` in front of the program.
        A single filename will only be included once.

        :param filename: The filename to include.
        """

        self.includes.add(filename)

    def comment(self, comment: str) -> None:
        """
        Inserts a block comment at the current position.

        :param comment: Comment string
        """

        self.statements.append(CommentStatement(comment))

    def statement(self, node: Statement) -> None:
        """
        Inserts a single statement at the current position.

        :param node: The statement to insert.
        """

        self.statements.append(node)

    def build_ast(self) -> Program:
        """
        Builds the final QASM program as an abstract syntax tree.

        :return: Final QASM program.
        """

        all_statements: list[Statement] = []
        all_statements.extend([Include(include) for include in self.includes])
        all_statements.extend(self.statements)

        return Program(all_statements, version="3.1")

    def build(self) -> str:
        """
        Builds the final QASM program as string.

        :return: Final QASM program.
        """

        program = self.build_ast()

        result = StringIO()
        ExtendedPrinter(result).visit(program)
        return result.getvalue()

    def __str__(self) -> str:
        return self.build()

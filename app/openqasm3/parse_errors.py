"""
Utils for formatting parsing errors.
"""

from antlr4 import Parser, RecognitionException
from antlr4.BufferedTokenStream import TokenStream
from antlr4.error.ErrorListener import ErrorListener
from antlr4.error.Errors import ParseCancellationException
from antlr4.error.ErrorStrategy import DefaultErrorStrategy
from openqasm3.parser import QASM3ParsingError

from app.model.CompileRequest import Node
from app.model.exceptions import DiagnosticError


class ParsingError(DiagnosticError):
    """
    Represents a parsing error of OpenQASM 3.
    """


class _RaiseOnErrorListener(ErrorListener):
    """
    Raises exception for all errors handled by this listener.

    This is taken from `openqasm3.parser._RaiseOnErrorListener`.
    """

    frontend_node = Node | None

    def __init__(self, node: Node | None):
        self.frontend_node = node

    def syntaxError(
        self,
        recognizer: object,
        offending_symbol: object,
        line: int,
        column: int,
        msg: str,
        exc: RecognitionException,
    ):
        raise ParsingError(f"L{line}:C{column}: {msg}", node=self.frontend_node)

    def _handle_antlr_error(self, error: RecognitionException) -> None:
        recognizer = Parser(TokenStream())
        recognizer.addErrorListener(self)

        # listener will raise as soon as it gets an error
        DefaultErrorStrategy().reportError(recognizer, error)

        # If no error is detected throw the original one
        raise error

    def _handle_parse_cancellation(self, error: ParseCancellationException) -> None:
        match error.args[0]:
            case RecognitionException():
                self._handle_antlr_error(error.__cause__)
            case _:
                raise error

    def handle_error(self, error: QASM3ParsingError) -> None:
        match error.__cause__:
            case RecognitionException():
                self._handle_antlr_error(error.__cause__)
            case ParseCancellationException():
                self._handle_parse_cancellation(error.__cause__)
            case _:
                raise error


def handle_parsing_error(error: QASM3ParsingError, node: Node | None):
    """
    Transforms a parser error to a leqo client error.

    :param error: Error to be transformed
    :param node: Node context
    """

    _RaiseOnErrorListener(node).handle_error(error)

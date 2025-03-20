from collections.abc import Iterable
from typing import Any, cast

from antlr4 import Token as Antlr4Token
from antlr4.CommonTokenStream import CommonTokenStream
from antlr4.InputStream import InputStream
from openqasm3._antlr._4_13.qasm3Lexer import qasm3Lexer
from pygments import token as PygmentTokens
from pygments.lexer import Lexer
from pygments.token import Token
from sphinx.application import Sphinx
from sphinx.highlighting import lexers


class OpenQasmLexer(Lexer):
    def map_token_types(self, token_type: Any) -> Token:
        match cast(int, token_type):
            case qasm3Lexer.AnnotationKeyword:
                return PygmentTokens.Name.Decorator

            case (
                qasm3Lexer.LBRACKET
                | qasm3Lexer.RBRACKET
                | qasm3Lexer.LBRACE
                | qasm3Lexer.RBRACE
            ):
                return PygmentTokens.Punctuation

            case qasm3Lexer.BinaryIntegerLiteral:
                return PygmentTokens.Number.Bin

            case qasm3Lexer.OctalIntegerLiteral:
                return PygmentTokens.Number.Oct

            case qasm3Lexer.DecimalIntegerLiteral:
                return PygmentTokens.Number.Integer

            case qasm3Lexer.HexIntegerLiteral:
                return PygmentTokens.Number.Hex

            case qasm3Lexer.FloatLiteral:
                return PygmentTokens.Number.Float

            case qasm3Lexer.DOUBLE_PLUS:
                return PygmentTokens.Operator

            case qasm3Lexer.Identifier:
                return PygmentTokens.Name.Other

            case qasm3Lexer.QUBIT | qasm3Lexer.LET:
                return PygmentTokens.Keyword

        return PygmentTokens.Generic

    def get_tokens_unprocessed(self, text: str) -> Iterable[tuple[int, Token, str]]:
        lexer = qasm3Lexer(InputStream(text))
        stream = CommonTokenStream(lexer)

        last_end = 0

        current_token: Antlr4Token = stream.LT(1)
        while current_token.type != Antlr4Token.EOF:
            stream.consume()

            if current_token.start != last_end:
                yield 0, PygmentTokens.Comment, text[last_end : current_token.start]
            last_end = current_token.stop + 1

            yield 0, self.map_token_types(current_token.type), current_token.text
            current_token = stream.LT(1)


def setup(_app: Sphinx) -> None:
    lexers["openqasm3"] = OpenQasmLexer()

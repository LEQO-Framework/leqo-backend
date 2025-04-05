from openqasm_pygments import OpenQASM2Lexer, OpenQASM3Lexer  # type: ignore
from sphinx.application import Sphinx
from sphinx.highlighting import lexers


def setup(_app: Sphinx) -> None:
    lexers["openqasm3"] = OpenQASM3Lexer()
    lexers["openqasm2"] = OpenQASM2Lexer()

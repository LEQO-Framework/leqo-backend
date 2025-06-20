from openqasm_pygments.qasm2 import OpenQASM2Lexer
from openqasm_pygments.qasm3 import OpenQASM3Lexer
from sphinx.application import Sphinx
from sphinx.highlighting import lexers


def setup(_app: Sphinx) -> None:
    lexers["openqasm3"] = OpenQASM3Lexer()
    lexers["openqasm2"] = OpenQASM2Lexer()

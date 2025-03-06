from textwrap import dedent

from openqasm3.ast import Identifier
from openqasm3.parser import parse
from openqasm3.printer import dumps
from openqasm3.visitor import QASMTransformer

from app.lib.transformer import Transformer


def normalize(program: str) -> str:
    """Normalize QASM-string."""
    return dedent(program).strip()


class AllToYDefault(QASMTransformer[None]):
    """Replaces all identifiers with y."""

    def visit_Identifier(self, node: Identifier) -> Identifier:
        """Replace name of all Identifiers with y."""
        node.name = "y"
        return node


class AllToYFixed(Transformer):
    """Like AllToYDefault but inherit from Transformer."""

    def visit_Identifier(self, node: Identifier) -> Identifier:
        """Replace name of all Identifiers with y."""
        node.name = "y"
        return node


def test_basic() -> None:
    """Covers the error fixed by the Transformer."""
    before = normalize("""
    const uint I = 100;
    x q[I];
    """)
    true = normalize("""
    const uint y = 100;
    y y[y];
    """)
    previous = normalize(dumps(AllToYDefault().visit(parse(before))))
    fixed = normalize(dumps(AllToYFixed().visit(parse(before))))
    assert true != previous
    assert true == fixed

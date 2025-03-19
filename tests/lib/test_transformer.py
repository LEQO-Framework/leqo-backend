from openqasm3.ast import Identifier
from openqasm3.parser import parse
from openqasm3.printer import dumps
from openqasm3.visitor import QASMTransformer

from app.lib.qasm_string import normalize
from app.lib.transformer import Transformer


class AllToYDefault(QASMTransformer[None]):
    """Replaces all identifiers with y."""

    def visit_Identifier(self, node: Identifier) -> Identifier:
        """Replace name of all Identifiers with y."""
        node.name = "y"
        return node


class AllToYFixed(Transformer[None]):
    """Like AllToYDefault but inherit from Transformer."""

    def visit_Identifier(self, node: Identifier) -> Identifier:
        """Replace name of all Identifiers with y."""
        node.name = "y"
        return node


def test_indecies() -> None:
    """Check if Transformer can handle variables in indices."""
    before = normalize("""
    x q[I];
    """)
    true = normalize("""
    y y[y];
    """)
    previous = normalize(dumps(AllToYDefault().visit(parse(before))))
    fixed = normalize(dumps(AllToYFixed().visit(parse(before))))
    assert true != previous
    assert true == fixed


def test_switch() -> None:
    """Check if Transformer can handle tuples in switches."""
    before = normalize("""
    switch (i) {
        case 1, B, C {
            x q;
            }
        }
    """)
    true = normalize("""
    switch (y) {
        case 1, y, y {
            y y;
            }
        }
    """)
    previous = normalize(dumps(AllToYDefault().visit(parse(before))))
    fixed = normalize(dumps(AllToYFixed().visit(parse(before))))
    assert true != previous
    assert true == fixed


class AllToYFixedContext(Transformer[bool]):
    """Check if context works."""

    def visit_Identifier(
        self,
        node: Identifier,
        context: bool | None = None,
    ) -> Identifier:
        """Replace name of all Identifiers with y."""
        if context is True:
            node.name = "y"
        return node


def test_context() -> None:
    """Check if Transformer can handle variables in indices."""
    before = normalize("""
    x q;
    """)
    true = normalize("""
    y y;
    """)
    none = normalize(dumps(AllToYFixedContext().visit(parse(before), False)))
    replaced = normalize(dumps(AllToYFixedContext().visit(parse(before), True)))
    assert before == none
    assert true == replaced


def test_all() -> None:
    """Check if Transformer can handle variables in indices."""
    before = normalize("""
    switch (i) {
        case 1, B, C {
            x q[I];
            }
        }
    """)
    true = normalize("""
    switch (y) {
        case 1, y, y {
            y y[y];
            }
        }
    """)
    none = normalize(dumps(AllToYFixedContext().visit(parse(before), False)))
    replaced = normalize(dumps(AllToYFixedContext().visit(parse(before), True)))
    assert before == none
    assert true == replaced

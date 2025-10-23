from openqasm3.ast import Identifier
from openqasm3.parser import parse
from openqasm3.printer import dumps
from openqasm3.visitor import QASMTransformer

from app.openqasm3.visitor import LeqoTransformer
from app.transformation_manager.utils import normalize_qasm_string


class AllToYDefault(QASMTransformer[None]):
    """
    Replaces all identifiers with y.
    """

    def visit_Identifier(self, node: Identifier) -> Identifier:
        """
        Replace name of all Identifiers with y.
        """
        node.name = "y"
        return node


class AllToYFixed(LeqoTransformer[None]):
    """
    Like AllToYDefault but inherit from Transformer.
    """

    def visit_Identifier(self, node: Identifier) -> Identifier:
        """
        Replace name of all Identifiers with y.
        """
        node.name = "y"
        return node


def test_indecies() -> None:
    """
    Check if Transformer can handle variables in indices.
    """
    before = normalize_qasm_string("""
    x q[I];
    """)
    true = normalize_qasm_string("""
    y y[y];
    """)
    previous = normalize_qasm_string(dumps(AllToYDefault().visit(parse(before))))
    fixed = normalize_qasm_string(dumps(AllToYFixed().visit(parse(before))))
    assert true != previous
    assert true == fixed


def test_switch() -> None:
    """
    Check if Transformer can handle tuples in switches.
    """
    before = normalize_qasm_string("""
    switch (i) {
        case 1, B, C {
            x q;
            }
        }
    """)
    true = normalize_qasm_string("""
    switch (y) {
        case 1, y, y {
            y y;
            }
        }
    """)
    previous = normalize_qasm_string(dumps(AllToYDefault().visit(parse(before))))
    fixed = normalize_qasm_string(dumps(AllToYFixed().visit(parse(before))))
    assert true != previous
    assert true == fixed


class AllToYFixedContext(LeqoTransformer[bool]):
    """
    Check if context works.
    """

    def visit_Identifier(
        self,
        node: Identifier,
        context: bool | None = None,
    ) -> Identifier:
        """
        Replace name of all Identifiers with y.
        """
        if context is True:
            node.name = "y"
        return node


def test_context() -> None:
    """
    Check if Transformer can handle variables in indices.
    """
    before = normalize_qasm_string("""
    x q;
    """)
    true = normalize_qasm_string("""
    y y;
    """)
    none = normalize_qasm_string(
        dumps(AllToYFixedContext().visit(parse(before), False)),
    )
    replaced = normalize_qasm_string(
        dumps(AllToYFixedContext().visit(parse(before), True)),
    )
    assert before == none
    assert true == replaced


def test_all() -> None:
    """
    Check if Transformer can handle variables in indices.
    """
    before = normalize_qasm_string("""
    switch (i) {
        case 1, B, C {
            x q[I];
            }
        }
    """)
    true = normalize_qasm_string("""
    switch (y) {
        case 1, y, y {
            y y[y];
            }
        }
    """)
    none = normalize_qasm_string(
        dumps(AllToYFixedContext().visit(parse(before), False)),
    )
    replaced = normalize_qasm_string(
        dumps(AllToYFixedContext().visit(parse(before), True)),
    )
    assert before == none
    assert true == replaced

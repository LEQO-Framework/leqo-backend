from openqasm3.parser import parse
from openqasm3.printer import dumps

from app.processing.post.sort_imports import SortImports
from app.processing.utils import normalize_qasm_string


def test_move_to_top() -> None:
    code = normalize_qasm_string("""
    include "stdgates.inc";
    qubit q0;
    include "qelib1.inc";
    qubit q1;
    """)
    expected = normalize_qasm_string("""
    include "stdgates.inc";
    include "qelib1.inc";
    qubit q0;
    qubit q1;
    """)
    actual = normalize_qasm_string(dumps(SortImports().visit(parse(code))))
    assert expected == actual

def test_remove_duplicates() -> None:
    code = normalize_qasm_string("""
    include "stdgates.inc";
    qubit q0;
    include "stdgates.inc";
    qubit q1;
    """)
    expected = normalize_qasm_string("""
    include "stdgates.inc";
    qubit q0;
    qubit q1;
    """)
    actual = normalize_qasm_string(dumps(SortImports().visit(parse(code))))
    assert expected == actual

def test_all() -> None:
    code = normalize_qasm_string("""
    include "stdgates.inc";
    qubit q0;
    include "stdgates.inc";
    include "qelib1.inc";
    qubit q1;
    include "stdgates.inc";
    include "qelib1.inc";
    qubit q2;
    """)
    expected = normalize_qasm_string("""
    include "stdgates.inc";
    include "qelib1.inc";
    qubit q0;
    qubit q1;
    qubit q2;
    """)
    actual = normalize_qasm_string(dumps(SortImports().visit(parse(code))))
    assert expected == actual

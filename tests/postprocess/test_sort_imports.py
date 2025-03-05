from openqasm3.parser import parse
from openqasm3.printer import dumps

from app.postprocess.sort_imports import SortImports
from tests.postprocess.helper import normalize


def test_basic() -> None:
    before = normalize("""
    include "stdgates.inc";
    bit[2] c;
    qubit[4] _all_qubits;
    let q = _all_qubits[0:3];
    x q[0];
    x q[1];
    cx q[0], q[2];
    cx q[1], q[2];
    include "stdgates.inc";
    include "qelib1.inc";
    ccx q[0], q[1], q[3];
    """)
    target = normalize("""
    include "stdgates.inc";
    include "qelib1.inc";
    bit[2] c;
    qubit[4] _all_qubits;
    let q = _all_qubits[0:3];
    x q[0];
    x q[1];
    cx q[0], q[2];
    cx q[1], q[2];
    ccx q[0], q[1], q[3];
    """)
    actual = normalize(dumps(SortImports().visit(parse(before))))
    assert target == actual

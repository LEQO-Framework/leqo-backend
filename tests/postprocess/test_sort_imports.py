from textwrap import dedent

from openqasm3.parser import parse
from openqasm3.printer import dumps

from app.postprocess.sort_imports import SortImports


def test_basic() -> None:
    before = dedent("""
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
    """).strip()
    target = dedent("""
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
    """).strip()
    actual = dedent(dumps(SortImports().transform(parse(before)))).strip()
    assert target == actual

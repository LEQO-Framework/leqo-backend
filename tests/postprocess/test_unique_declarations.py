from openqasm3.parser import parse
from openqasm3.printer import dumps

from app.postprocess.unique_declarations import UniqueDeclarations
from tests.postprocess.helper import normalize


def get_result(program: str) -> str:
    return normalize(dumps(UniqueDeclarations().transform(parse(program))))


def test_duplicate_constant() -> None:
    # Rename
    before = normalize("""
    const uint I = 100;
    const uint I = 10;
    qubit[I] q;
    const uint I = 6;
    x q[I];
    const uint I = 2;
    x q[I];
    """)
    target = normalize("""
    const uint I = 100;
    const uint I1 = 10;
    qubit[I1] q;
    const uint I2 = 6;
    x q[I2];
    const uint I3 = 2;
    x q[I3];
    """)
    actual = get_result(before)
    assert target == actual


def test_duplicate_classical() -> None:
    # Rename
    before = normalize("""
    bit[10] b;
    bit[10] b;
    bit[10] b;
    bit[10] b;
    """)
    target = normalize("""
    bit[10] b;
    """)
    actual = get_result(before)
    assert target == actual


def test_duplicate_qubit() -> None:
    # Removal
    before = normalize("""
    qubit[5] q;
    qubit[5] q;
    qubit[5] q;
    qubit[5] q;
    x q[0];
    """)
    target = normalize("""
    qubit[5] q;
    x q[0];
    """)
    actual = get_result(before)
    assert target == actual

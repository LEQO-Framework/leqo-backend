from openqasm3.parser import parse
from openqasm3.printer import dumps

from app.postprocess.connect_variables import ConnectVariables
from tests.postprocess.helper import normalize


def test_declaration_reduction() -> None:
    """One connection variable should be only declared once."""
    before = normalize("""
    qubit q1;
    qubit q2;
    qubit q3;
    """)
    target = normalize("""
    qubit connect1;
    qubit q3;
    """)
    actual = normalize(dumps(ConnectVariables([["q1", "q2"]]).visit(parse(before))))
    assert target == actual


def test_renaming() -> None:
    """A connection should result in the renaming of the corresponding usages."""
    before = normalize("""
    x q1;
    x q2;
    ccx q1, q2, q3;
    """)
    target = normalize("""
    x connect1;
    x connect1;
    ccx connect1, connect1, q3;
    """)
    actual = normalize(dumps(ConnectVariables([["q1", "q2"]]).visit(parse(before))))
    assert target == actual

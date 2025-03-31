from openqasm3.parser import parse
from openqasm3.printer import dumps

from app.processing.post.connect_variables import ConnectVariables
from app.processing.utils import normalize_qasm_string


def test_declaration_reduction() -> None:
    """One connection variable should be only declared once."""
    before = normalize_qasm_string("""
    qubit q1;
    qubit q2;
    qubit q3;
    """)
    target = normalize_qasm_string("""
    qubit connect1;
    qubit q3;
    """)
    actual = normalize_qasm_string(
        dumps(ConnectVariables([["q1", "q2"]]).visit(parse(before))),
    )
    assert target == actual


def test_renaming() -> None:
    """A connection should result in the renaming of the corresponding usages."""
    before = normalize_qasm_string("""
    x q1;
    x q2;
    ccx q1, q2, q3;
    """)
    target = normalize_qasm_string("""
    x connect1;
    x connect1;
    ccx connect1, connect1, q3;
    """)
    actual = normalize_qasm_string(
        dumps(ConnectVariables([["q1", "q2"]]).visit(parse(before))),
    )
    assert target == actual


def test_multiple_connections() -> None:
    """Test multiple connections + declamations."""
    before = normalize_qasm_string("""
    qubit q1;
    qubit q2;
    qubit q3;
    qubit q4;
    x q1;
    x q2;
    ccx q1, q2, q3;
    ccx q2, q3, q4;
    """)
    target = normalize_qasm_string("""
    qubit connect1;
    qubit connect2;
    x connect1;
    x connect2;
    ccx connect1, connect2, connect1;
    ccx connect2, connect1, connect2;
    """)
    actual = normalize_qasm_string(
        dumps(ConnectVariables([["q1", "q3"], ["q2", "q4"]]).visit(parse(before))),
    )
    assert target == actual

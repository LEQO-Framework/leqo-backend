from openqasm3.parser import parse

from app.lib.qasm_string import normalize
from app.model.dataclass import IOInfo
from app.preprocessing.io_parser import IOParse


def test_basic() -> None:
    """Check if Transformer can handle variables in indices."""
    code = normalize("""
    @leqo.input 0
    qubit[5] q0;
    @leqo.input 1
    qubit[5] q1;

    @leqo.output 0
    let _out0 = q0[0] ++ q1[1];
    @leqo.output 1
    let _out1 = q0[1] ++ q1[3];

    @leqo.reusable
    let _reuse = q0[2:4];
    """)
    expected = IOInfo()
    actual = IOParse().extract_io_info(parse(code))
    assert expected == actual

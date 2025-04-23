import pytest
from openqasm3.ast import Program
from openqasm3.printer import dumps

from app.converter.qasm_converter import QASMConversionError, QASMConverter
from app.processing.utils import normalize_qasm_string


# Helper functions # # # # #
def check_out(out: Program, expected: str) -> None:
    actual_circuit = normalize_qasm_string(dumps(out))
    expected_circuit = normalize_qasm_string(expected)
    assert actual_circuit == expected_circuit


def test_qubit_conversion() -> None:
    converter = QASMConverter()
    input_qasm2 = """OPENQASM 2.0;
    qreg q[1];
    qreg qubits[10];
    creg c[1];
    creg bits[12];
    """
    expected = """OPENQASM 3.1;
    qubit[1] q;
    qubit[10] qubits;
    bit[1] c;
    bit[12] bits;"""
    check_out(converter.parse_to_qasm3(input_qasm2), expected)


def test_measure_statement_conversion() -> None:
    converter = QASMConverter()
    input_qasm2 = """
    OPENQASM 2.0;
    measure q->c;
    measure q[0] -> c[1];
    """
    expected = """
    OPENQASM 3.1;
    c = measure q;
    c[1] = measure q[0];
    """
    check_out(converter.parse_to_qasm3(input_qasm2), expected)


def test_raise_on_opaque() -> None:
    converter = QASMConverter()
    input_qasm2 = """
    OPENQASM 2.0;
    opaque custom_gate (a,b,c) p,q,r;
    """
    with pytest.raises(QASMConversionError):
        converter.parse_to_qasm3(input_qasm2)


def test_std_header_conversion() -> None:
    converter = QASMConverter()
    input_qasm2 = """
    OPENQASM 2.0;
    """
    expected = """
    OPENQASM 3.1;
    """
    check_out(converter.parse_to_qasm3(input_qasm2), expected)


def test_unsupported_qasm_version_exception() -> None:
    with pytest.raises(QASMConversionError):
        QASMConverter().parse_to_qasm3("OPENQASM 1.0;")


def test_non_raise_on_qasm_2_1() -> None:
    # Test that a valid OPENQASM 2.1 statement does not raise an exception.
    converter = QASMConverter()
    input_qasm2 = """
            OPENQASM 2.1;
            """
    expected = """
            OPENQASM 3.1;
            """
    check_out(converter.parse_to_qasm3(input_qasm2), expected)


def test_lib_replace() -> None:
    converter = QASMConverter()
    input_qasm2 = """
    OPENQASM 2.0;
    include "qelib1.inc";
    """
    expected = """
    OPENQASM 3.1;
    include "stdgates.inc";
    """
    check_out(converter.parse_to_qasm3(input_qasm2), expected)


def test_raise_on_no_version() -> None:
    # Test that a valid OPENQASM 2.1 statement does not raise an exception.
    converter = QASMConverter()
    input_qasm2 = """
    include "stdgates.inc";
    """
    with pytest.raises(QASMConversionError):
        converter.parse_to_qasm3(input_qasm2)


def test_single_custom_gate() -> None:
    converter = QASMConverter()
    input_qasm2 = """
    OPENQASM 2.0;
    include "qelib1.inc";
    rccx q[0], q[1], q[2];
    """
    expected = """
    OPENQASM 3.1;
    include "stdgates.inc";
    gate rccx a, b, c {
        u2(0, pi) c;
        u3(0, 0, pi / 4) c;
        cx b, c;
        u3(0, 0, -pi / 4) c;
        cx a, c;
        u3(0, 0, pi / 4) c;
        cx b, c;
        u3(0, 0, -pi / 4) c;
        u2(0, pi) c;
    }
    rccx q[0], q[1], q[2];
    """
    check_out(converter.parse_to_qasm3(input_qasm2), expected)


def test_simple_annotation_convert() -> None:
    converter = QASMConverter()
    input_qasm2 = """
    OPENQASM 2.0;
    //@leqo.input 0
    qreg q0[5];
    //    @some_other xyz :)
    qreg q1[5];
    """
    expected = """
    OPENQASM 3.1;
    @leqo.input 0
    qubit[5] q0;
    @some_other xyz :)
    qubit[5] q1;
    """
    check_out(converter.parse_to_qasm3(input_qasm2), expected)


def test_alias_with_annotation() -> None:
    converter = QASMConverter()
    input_qasm2 = """
    OPENQASM 2.0;
    qreg q0[5];
    // @leqo.input 0
    // let _out = q0[1:2];
    //     @leqo.reusable
    //let _reuse = q0[3];
    // let xxx = not_converted();
    """
    expected = """
    OPENQASM 3.1;
    qubit[5] q0;
    @leqo.input 0
    let _out = q0[1:2];
    @leqo.reusable
    let _reuse = q0[3];
    """
    check_out(converter.parse_to_qasm3(input_qasm2), expected)


def test_uncompute_block() -> None:
    converter = QASMConverter()
    input_qasm2 = """
    OPENQASM 2.0;
    qreg q0[5];
    // @leqo.uncompute start
    // @leqo.reusable
    // let _reuse = q0[3];
    // @leqo.uncompute end
    qreg q1[5];
    """
    expected = """
    OPENQASM 3.1;
    qubit[5] q0;
    @leqo.uncompute
    if (false) {
        @leqo.reusable
        let _reuse = q0[3];
    }
    qubit[5] q1;
    """
    check_out(converter.parse_to_qasm3(input_qasm2), expected)


def test_unsupported_gate_conversion() -> None:
    input_qasm2 = """
    OPENQASM 2.0;
    include "qelib1.inc";
    qreg q[5];
    u0(1) q[0];
    u(1,2,3) q[0];
    sxdg q[0];
    csx q[0], q[1];
    cu1(0.5) q[0], q[1];
    cu3(1,2,3) q[0], q[1];
    rxx(0.5) q[0], q[1];
    rzz(0.5) q[0], q[1];
    rccx q[0], q[1], q[2];
    rc3x q[0], q[1], q[2], q[3];
    c3x q[0], q[1], q[2], q[3];
    c3sqrtx q[0], q[1], q[2], q[3];
    c4x q[0], q[1], q[2], q[3], q[4];
    """
    expected = """
    OPENQASM 3.1;
    include "stdgates.inc";
    gate c3sqrtx a, b, c, d {
      ctrl(3) @ sx a, b, c, d;
    }
    gate c3x a, b, c, d {
      ctrl(3) @ x a, b, c, d;
    }
    gate c4x a, b, c, d, e {
      ctrl(4) @ x a, b, c, d, e;
    }
    gate csx a, b {
      ctrl @ sx a, b;
    }
    gate cu1(lambda) a, b {
      u3(0, 0, lambda / 2) a;
      cx a, b;
      u3(0, 0, -lambda / 2) b;
      cx a, b;
      u3(0, 0, lambda / 2) b;
    }
    gate cu3(theta, phi, lambda) c, t {
      u3(0, 0, (lambda + phi) / 2) c;
      u3(0, 0, (lambda - phi) / 2) t;
      cx c, t;
      u3(-theta / 2, 0, -(phi + lambda) / 2) t;
      cx c, t;
      u3(theta / 2, phi, 0) t;
    }
    gate rc3x a, b, c, d {
      u2(0, pi) d;
      u3(0, 0, pi / 4) d;
      cx c, d;
      u3(0, 0, -pi / 4) d;
      u2(0, pi) d;
      cx a, d;
      u3(0, 0, pi / 4) d;
      cx b, d;
      u3(0, 0, -pi / 4) d;
      cx a, d;
      u3(0, 0, pi / 4) d;
      cx b, d;
      u3(0, 0, -pi / 4) d;
      u2(0, pi) d;
      u3(0, 0, pi / 4) d;
      cx c, d;
      u3(0, 0, -pi / 4) d;
      u2(0, pi) d;
    }
    gate rccx a, b, c {
      u2(0, pi) c;
      u3(0, 0, pi / 4) c;
      cx b, c;
      u3(0, 0, -pi / 4) c;
      cx a, c;
      u3(0, 0, pi / 4) c;
      cx b, c;
      u3(0, 0, -pi / 4) c;
      u2(0, pi) c;
    }
    gate rxx(theta) a, b {
      u3(pi / 2, theta, 0) a;
      h b;
      cx a, b;
      u1(-theta) b;
      cx a, b;
      h b;
      u2(-pi, pi - theta) b;
    }
    gate rzz(theta) a, b {
      cx a, b;
      u3(0, 0, theta) b;
      cx a, b;
    }
    gate sxdg a {
      s a;
      h a;
      s a;
    }
    gate u(theta, phi, lambda) q {
      u3(theta, phi, lambda) q;
    }
    gate u0(gamma) q {
      u3(0, 0, 0) q;
    }
    qubit[5] q;
    u0(1) q[0];
    u(1, 2, 3) q[0];
    sxdg q[0];
    csx q[0], q[1];
    cu1(0.5) q[0], q[1];
    cu3(1, 2, 3) q[0], q[1];
    rxx(0.5) q[0], q[1];
    rzz(0.5) q[0], q[1];
    rccx q[0], q[1], q[2];
    rc3x q[0], q[1], q[2], q[3];
    c3x q[0], q[1], q[2], q[3];
    c3sqrtx q[0], q[1], q[2], q[3];
    c4x q[0], q[1], q[2], q[3], q[4];
    """
    converter = QASMConverter()
    check_out(converter.parse_to_qasm3(input_qasm2), expected)

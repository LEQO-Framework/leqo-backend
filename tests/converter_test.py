import os
import pytest
from qiskit.qasm3 import loads
from app.model.qasm_converter import QASMConversionError, convert_qasm2_to_qasm3


def test_qubit_conversion():
    input_qasm2 = """OPENQASM 2.0;
    include "qelib1.inc";
    qreg q[1];
    qreg qubits[10];
    creg c[1];
    creg bits[12];
    """
    expected = f"""OPENQASM 3.0;
    include "stdgates.inc";
    {get_qasm3_def()}
    qubit[1] q;
    qubit[10] qubits;
    bit[1] c;
    bit[12] bits;"""
    check_out(convert_qasm2_to_qasm3(input_qasm2), expected)


def test_measure_statement_conversion():
    input_qasm2 = """
    OPENQASM 2.0;
    include "qelib1.inc";
    qreg q[2];
    creg c[2];
    measure q->c;
    measure q[0] -> c[1];
    """
    expected = f"""
    OPENQASM 3.0;
    include "stdgates.inc";
    {get_qasm3_def()}
    qubit[2] q;
    bit[2] c;
    c = measure q;
    c[1] = measure q[0];
    """
    check_out(convert_qasm2_to_qasm3(input_qasm2), expected)


def test_opaque_comment_conversion():
    input_qasm2 = """
    OPENQASM 2.0;
    include "qelib1.inc";
    qreg q[2];
    creg c[2];
    opaque custom_gate (a,b,c) p,q,r;
    """
    expected = f"""
    OPENQASM 3.0;
    include "stdgates.inc";
    {get_qasm3_def()}
    qubit[2] q;
    bit[2] c;
    // opaque custom_gate (a,b,c) p,q,r;
    """
    check_out(convert_qasm2_to_qasm3(input_qasm2), expected)


def test_std_header_conversion():
    input_qasm2 = """
    OPENQASM 2.0;
    include "qelib1.inc";
    qreg q[1];
    """
    expected = f"""
    OPENQASM 3.0;
    include "stdgates.inc";
    {get_qasm3_def()}
    qubit[1] q;
    """
    check_out(convert_qasm2_to_qasm3(input_qasm2), expected)


def test_unsupported_gate_conversion():
    input_qasm2 = """
    OPENQASM 2.0;
    include "qelib1.inc";
    qreg q[5];
    u(1,2,3) q[0];
    sxdg q[0];
    csx q[0], q[1];
    cu1(0.5) q[0], q[1];
    cu3(1,2,3) q[0], q[1];
    rzz(0.5) q[0], q[1];
    rccx q[0], q[1], q[2];
    rc3x q[0], q[1], q[2], q[3];
    c3x q[0], q[1], q[2], q[3];
    c3sqrtx q[0], q[1], q[2], q[3];
    c4x q[0], q[1], q[2], q[3], q[4];
    """
    expected = f"""
    OPENQASM 3.0;   
    include "stdgates.inc";
    {get_qasm3_def()}
    qubit[5] q;
    u(1,2,3) q[0];
    sxdg q[0];
    csx q[0], q[1];
    cu1(0.5) q[0], q[1];
    cu3(1,2,3) q[0], q[1];
    rzz(0.5) q[0], q[1];
    rccx q[0], q[1], q[2];
    rc3x q[0], q[1], q[2], q[3];
    c3x q[0], q[1], q[2], q[3];
    c3sqrtx q[0], q[1], q[2], q[3];
    c4x q[0], q[1], q[2], q[3], q[4];
    """
    check_out(convert_qasm2_to_qasm3(input_qasm2), expected)


def test_unsupported_qasm_version_exception():
    with pytest.raises(
        QASMConversionError,
        match="Unsupported QASM version. Only 'OPENQASM 2.x' is allowed.",
    ):
        convert_qasm2_to_qasm3("OPENQASM 3.0;")


def test_unsupported_library_exception():
    with pytest.raises(
        QASMConversionError,
        match="Unsupported library included. Only 'qelib1.inc' is allowed.",
    ):
        convert_qasm2_to_qasm3('include "otherlib.inc";')


def test_valid_qasm_version():
    # Test that a valid OPENQASM 2.1 statement does not raise an exception.
    input_qasm2 = """
            OPENQASM 2.1;
            include "qelib1.inc";
            qreg q[1];
            """
    expected = f"""
            OPENQASM 3.0;
            include "stdgates.inc";
            {get_qasm3_def()}
            qubit[1] q;
            """
    result = convert_qasm2_to_qasm3(input_qasm2)
    check_out(result, expected)


# Helper functions # # # # #
def check_out(out, expected):
    actual_circuit = loads(out)
    expected_circuit = loads(expected)
    assert actual_circuit == expected_circuit


def get_qasm3_def():
    lib_dir = os.path.dirname(os.path.dirname(__file__)) + "\\app\model\qasm_lib"
    return open(os.path.join(lib_dir, "qasm3_qelib1.qasm"), encoding="utf-8").read()

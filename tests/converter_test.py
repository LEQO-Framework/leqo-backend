import os

import pytest
from qiskit.qasm3 import loads

from app.converter.qasm_converter import QASMConversionError, QASMConverter


def test_qubit_conversion() -> None:
    converter = QASMConverter()
    input_qasm2 = """OPENQASM 2.0;
    include "qelib1.inc";
    qreg q[1];
    qreg qubits[10];
    creg c[1];
    creg bits[12];
    """
    expected = f"""OPENQASM 3.0;
    include "stdgates.inc";
    {converter.create_unsupported_gates_snippet(input_qasm2)}
    qubit[1] q;
    qubit[10] qubits;
    bit[1] c;
    bit[12] bits;"""
    check_out(converter.qasm2_to_qasm3(input_qasm2), expected)


def test_measure_statement_conversion() -> None:
    converter = QASMConverter()
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
    {converter.create_unsupported_gates_snippet(input_qasm2)}
    qubit[2] q;
    bit[2] c;
    c = measure q;
    c[1] = measure q[0];
    """
    check_out(converter.qasm2_to_qasm3(input_qasm2), expected)


def test_opaque_comment_conversion() -> None:
    converter = QASMConverter()
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
    {converter.create_unsupported_gates_snippet(input_qasm2)}
    qubit[2] q;
    bit[2] c;
    // opaque custom_gate (a,b,c) p,q,r;
    """
    check_out(converter.qasm2_to_qasm3(input_qasm2), expected)


def test_std_header_conversion() -> None:
    converter = QASMConverter()
    input_qasm2 = """
    OPENQASM 2.0;
    include "qelib1.inc";
    qreg q[1];
    """
    expected = f"""
    OPENQASM 3.0;
    include "stdgates.inc";
    {converter.create_unsupported_gates_snippet(input_qasm2)}
    qubit[1] q;
    """
    check_out(converter.qasm2_to_qasm3(input_qasm2), expected)


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
    OPENQASM 3.0;   
    include "stdgates.inc";
        
    // Generated helper gates for unsupported QASM 2.x gates ////////
    
    // Helper gate for u0 
    gate u0(gamma) q 
    {
        u3(0,0,0) q;
    }
    
    // Helper gate for u 
    gate u(theta,phi,lambda) q 
    {
        u3(theta,phi,lambda) q;
    }
    
    // Helper gate for sxdg 
    gate sxdg a 
    {
        s a; h a; s a;
    }
    
    // Helper gate for csx 
    gate csx a, b 
    {
        ctrl @ sx a, b;
    }
    
    // Helper gate for cu1 
    gate cu1(lambda) a, b 
    {
        u3(0,0,lambda/2) a; cx a,b; u3(0,0,-lambda/2) b; cx a,b; u3(0,0,lambda/2) b;
    }
    
    // Helper gate for cu3 
    gate cu3(theta,phi,lambda) c, t 
    {
        u3(0,0,(lambda+phi)/2) c; u3(0,0,(lambda-phi)/2) t; cx c,t; u3(-theta/2,0,-(phi+lambda)/2) t; cx c,t; u3(theta/2,phi,0) t;
    }
    
    // Helper gate for rxx 
    gate rxx(theta) a, b 
    {
        u3(pi/2, theta, 0) a; h b; cx a,b; u1(-theta) b; cx a,b; h b; u2(-pi, pi-theta) b;
    }
    
    // Helper gate for rzz 
    gate rzz(theta) a,b 
    {
        cx a,b; u3(0,0,theta) b; cx a,b;
    }
    
    // Helper gate for rccx 
    gate rccx a,b,c 
    {
        u2(0,pi) c; u3(0,0,pi/4) c; cx b, c; u3(0,0,-pi/4) c; cx a, c; u3(0,0,pi/4) c; cx b, c; u3(0,0,-pi/4) c; u2(0,pi) c;
    }
    
    // Helper gate for rc3x 
    gate rc3x a,b,c,d 
    {
        u2(0,pi) d; u3(0,0,pi/4) d; cx c,d; u3(0,0,-pi/4) d; u2(0,pi) d; cx a,d; u3(0,0,pi/4) d; cx b,d; u3(0,0,-pi/4) d; cx a,d; u3(0,0,pi/4) d; cx b,d; u3(0,0,-pi/4) d; u2(0,pi) d; u3(0,0,pi/4) d; cx c,d; u3(0,0,-pi/4) d; u2(0,pi) d;
    }
    
    // Helper gate for c3x 
    gate c3x a,b,c,d 
    {
        ctrl (3) @ x a, b, c, d;
    }
    
    // Helper gate for c3sqrtx 
    gate c3sqrtx a,b,c,d 
    {
        ctrl (3) @ sx a, b, c, d;
    }
    
    // Helper gate for c4x 
    gate c4x a,b,c,d,e 
    {
        ctrl (4) @ x a, b, c, d, e;
    }
    
    
    /////////////////////////////////////////////////////////////////

    qubit[5] q;
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
    converter = QASMConverter()
    check_out(converter.qasm2_to_qasm3(input_qasm2), expected)


def test_unsupported_qasm_version_exception() -> None:
    with pytest.raises(
        QASMConversionError,
        match="Unsupported QASM version. Only 'OPENQASM 2.x' is allowed.",
    ):
        QASMConverter().qasm2_to_qasm3("OPENQASM 3.0;")


def test_unsupported_library_exception() -> None:
    with pytest.raises(
        QASMConversionError,
        match="Unsupported library included. Only 'qelib1.inc' is allowed.",
    ):
        QASMConverter().qasm2_to_qasm3('include "otherlib.inc";')


def test_valid_qasm_version() -> None:
    # Test that a valid OPENQASM 2.1 statement does not raise an exception.
    converter = QASMConverter()
    input_qasm2 = """
            OPENQASM 2.1;
            include "qelib1.inc";
            qreg q[1];
            """
    expected = f"""
            OPENQASM 3.0;
            include "stdgates.inc";
            {converter.create_unsupported_gates_snippet(input_qasm2)}
            qubit[1] q;
            """
    check_out(converter.qasm2_to_qasm3(input_qasm2), expected)


# Helper functions # # # # #
def check_out(out: str, expected: str) -> None:
    actual_circuit = loads(out)
    expected_circuit = loads(expected)
    assert actual_circuit == expected_circuit

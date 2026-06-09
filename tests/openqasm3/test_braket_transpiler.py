import io
from contextlib import redirect_stdout

import pytest
from openqasm3.parser import parse

from app.openqasm3.braket_provider import BraketProvider
from app.openqasm3.universal_transpiler import UniversalTranspiler


def _transpile_braket(source: str) -> str:
    code = UniversalTranspiler(BraketProvider()).visit_Program(parse(source))
    compile(code, "<generated-braket>", "exec")
    assert "TODO:" not in code
    assert "Note: Measurement of" not in code
    assert "UNKNOWN_" not in code
    return code


def test_bell_state_uses_index_register_and_braket_gates() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit[2] leqo_reg;
    h leqo_reg[0];
    cx leqo_reg[0], leqo_reg[1];
    measure leqo_reg[0];
    measure leqo_reg[1];
    '''

    code = _transpile_braket(source)

    assert "leqo_reg = list(range(2))" in code
    assert "c = Circuit()" in code
    assert "c.h(" in code
    assert "c.cnot(" in code
    assert "c.measure(" in code


def test_two_qubit_parameterized_gate_orders_qubits_before_angle() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    input angle theta;
    qubit[2] leqo_reg;
    cphaseshift(theta) leqo_reg[0], leqo_reg[1];
    '''

    code = _transpile_braket(source)

    # Braket order is (qubits..., angle): both qubits precede the parameter.
    assert "c.cphaseshift(leqo_reg[0], leqo_reg[1], theta)" in code


def test_two_qubit_fixed_gate_passes_two_scalar_operands() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit[2] leqo_reg;
    swap leqo_reg[0], leqo_reg[1];
    '''

    code = _transpile_braket(source)

    assert "c.swap(leqo_reg[0], leqo_reg[1])" in code


def test_gate_name_mapping_translates_qiskit_names_to_braket() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit[3] leqo_reg;
    cx leqo_reg[0], leqo_reg[1];
    ccx leqo_reg[0], leqo_reg[1], leqo_reg[2];
    sdg leqo_reg[0];
    tdg leqo_reg[1];
    sx leqo_reg[2];
    '''

    code = _transpile_braket(source)

    assert "c.cnot(" in code
    assert "c.ccnot(" in code
    assert "c.si(" in code
    assert "c.ti(" in code
    assert "c.v(" in code
    assert "c.cx(" not in code


def test_parameter_input_uses_free_parameter_and_suppresses_run() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    input angle theta;
    qubit[1] leqo_reg;
    rx(theta) leqo_reg[0];
    measure leqo_reg[0];
    '''

    code = _transpile_braket(source)

    assert "from braket.circuits import Circuit, FreeParameter" in code
    assert "theta = FreeParameter('theta')" in code
    assert "c.rx(leqo_reg[0], theta)" in code
    assert "device.run(" not in code
    assert "Provide explicit values before execution" in code


def test_float_input_uses_free_parameter() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    input float theta;
    qubit[1] leqo_reg;
    rz(theta) leqo_reg[0];
    measure leqo_reg[0];
    '''

    code = _transpile_braket(source)

    assert "theta = FreeParameter('theta')" in code
    assert "device.run(" not in code


def test_fully_bound_circuit_emits_run_block() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit[2] leqo_reg;
    h leqo_reg[0];
    cx leqo_reg[0], leqo_reg[1];
    measure leqo_reg[0];
    measure leqo_reg[1];
    '''

    code = _transpile_braket(source)

    assert "device = LocalSimulator()" in code
    assert "device.run(c, shots=500)" in code
    assert "measurement_counts" in code


def test_for_loop_is_kept_as_host_side_python_loop() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit[1] leqo_reg;
    for uint i in [0:2] {
        h leqo_reg[0];
    }
    '''

    code = _transpile_braket(source)

    assert "for i in range(0, 3):" in code
    assert "c.h(" in code


def test_circuit_without_measurement_has_no_run_block() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit[1] leqo_reg;
    h leqo_reg[0];
    '''

    code = _transpile_braket(source)

    assert "device = LocalSimulator()" not in code
    assert "device.run(" not in code
    assert "c.h(" in code


def test_reset_fails_loudly() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit[1] leqo_reg;
    reset leqo_reg[0];
    '''

    with pytest.raises(NotImplementedError, match="reset"):
        _transpile_braket(source)


def test_if_block_fails_loudly() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit[1] leqo_reg;
    bit[1] c;
    measure leqo_reg[0] -> c[0];
    if (c[0]) {
        x leqo_reg[0];
    }
    '''

    with pytest.raises(NotImplementedError, match="branching"):
        _transpile_braket(source)


def test_while_loop_fails_loudly() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit[1] leqo_reg;
    uint[8] n = 0;
    while (n < 3) {
        x leqo_reg[0];
        n += 1;
    }
    '''

    with pytest.raises(NotImplementedError):
        _transpile_braket(source)


def test_typed_classical_declaration_fails_loudly() -> None:
    source = '''
    OPENQASM 3.0;
    uint[8] counter = 0;
    '''

    with pytest.raises(NotImplementedError, match="classical"):
        _transpile_braket(source)


def test_declared_output_fails_loudly() -> None:
    source = '''
    OPENQASM 3.0;
    output bit result;
    '''

    with pytest.raises(NotImplementedError, match="output"):
        _transpile_braket(source)


def test_measurement_driven_while_fails_loudly() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit[1] leqo_reg;
    bit[1] c;
    measure leqo_reg[0] -> c[0];
    while (c[0]) {
        x leqo_reg[0];
        measure leqo_reg[0] -> c[0];
    }
    '''

    with pytest.raises(NotImplementedError):
        _transpile_braket(source)


def test_unknown_gate_fails_loudly() -> None:
    source = '''
    OPENQASM 3.0;
    qubit[1] leqo_reg;
    totally_made_up_gate leqo_reg[0];
    '''

    with pytest.raises(NotImplementedError, match="Braket"):
        _transpile_braket(source)


def test_fully_bound_bell_executes_on_local_simulator() -> None:
    """Proof-of-concept: the generated Braket program runs on the LocalSimulator."""
    pytest.importorskip("braket")

    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit[2] leqo_reg;
    h leqo_reg[0];
    cx leqo_reg[0], leqo_reg[1];
    measure leqo_reg[0];
    measure leqo_reg[1];
    '''

    code = _transpile_braket(source)
    namespace: dict = {}
    with redirect_stdout(io.StringIO()):
        exec(code, namespace, namespace)

    counts = namespace["counts"]
    assert sum(counts.values()) == 500
    # An ideal Bell state only ever yields the correlated 00/11 outcomes.
    assert set(counts.keys()) <= {"00", "11"}

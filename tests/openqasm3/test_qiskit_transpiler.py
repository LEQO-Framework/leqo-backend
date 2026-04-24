import io
from contextlib import redirect_stdout

import pytest
from openqasm3.parser import parse

from app.openqasm3.qiskit_provider import QiskitProvider
from app.openqasm3.universal_transpiler import UniversalTranspiler


def _transpile_qiskit(source: str) -> str:
    code = UniversalTranspiler(QiskitProvider()).visit_Program(parse(source))
    compile(code, "<generated-qiskit>", "exec")
    assert "TODO:" not in code
    assert "UNKNOWN_" not in code
    return code


def _execute_qiskit(source: str) -> tuple[str, dict]:
    code = _transpile_qiskit(source)
    namespace: dict = {}
    with redirect_stdout(io.StringIO()):
        exec(code, namespace, namespace)
    return code, namespace


def test_internal_integer_state_uses_typed_classical_var() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    uint[32] counter = 0;
    qubit q;
    while (counter < 3) {
        x q;
        counter += 1;
    }
    '''

    code = _transpile_qiskit(source)

    assert "counter = ClassicalRegister" not in code
    assert "qc.add_var(expr.Var.new('counter', types.Uint(32)), 0)" in code
    assert "qc.store(counter, expr.add(counter, 1))" in code


def test_boolean_state_uses_boolean_semantics() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    bool flag = false;
    qubit q;
    if (flag == false) {
        x q;
    } else {
        h q;
    }
    '''

    code = _transpile_qiskit(source)

    assert "flag = ClassicalRegister" not in code
    assert "qc.add_var(expr.Var.new('flag', types.Bool()), False)" in code
    assert "types.Uint(32)" not in code
    assert "with _else:" in code


def test_bit_declaration_uses_classical_register_storage() -> None:
    source = '''
    OPENQASM 3.0;
    bit c;
    '''

    code = _transpile_qiskit(source)

    assert "c = ClassicalRegister(1, 'c')" in code
    assert "qc.add_register(c)" in code


def test_measurement_declaration_uses_register_path_and_executes() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit q;
    bit c = measure q;
    '''

    code, namespace = _execute_qiskit(source)

    assert "c = ClassicalRegister(1, 'c')" in code
    assert "qc.measure(q, c)" in code
    assert namespace["counts"] == {"0": 500}


def test_scalar_bit_measurement_target_uses_register_and_executes() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit q;
    bit c;
    measure q -> c;
    '''

    code, namespace = _execute_qiskit(source)

    assert "c = ClassicalRegister(1, 'c')" in code
    assert "qc.measure(q, c)" in code
    assert namespace["counts"] == {"0": 500}


def test_register_measurement_declaration_measures_whole_register_and_executes() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit[2] q;
    bit[2] c = measure q;
    '''

    code, namespace = _execute_qiskit(source)

    assert "c = ClassicalRegister(2, 'c')" in code
    assert "qc.measure(q, c)" in code
    assert namespace["counts"] == {"00": 500}


def test_register_measurement_statement_measures_whole_register_and_executes() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit[2] q;
    bit[2] c;
    measure q -> c;
    '''

    code, namespace = _execute_qiskit(source)

    assert "c = ClassicalRegister(2, 'c')" in code
    assert "qc.measure(q, c)" in code
    assert namespace["counts"] == {"00": 500}


def test_indexed_gate_application_uses_subscripted_qubit() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit[2] q;
    x q[1];
    '''

    code = _transpile_qiskit(source)

    assert "qc.x(q[1])" in code


def test_indexed_measurement_target_uses_subscripted_bits_and_executes() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit[2] q;
    bit[2] c;
    x q[1];
    measure q[1] -> c[0];
    '''

    code, namespace = _execute_qiskit(source)

    assert "qc.measure(q[1], c[0])" in code
    assert namespace["counts"] == {"01": 500}


def test_uninitialized_integer_then_assignment_uses_store() -> None:
    source = '''
    OPENQASM 3.0;
    uint[8] x;
    x = 3;
    '''

    code = _transpile_qiskit(source)

    assert "x = expr.Var.new('x', types.Uint(8))" in code
    assert "qc.add_uninitialized_var(x)" in code
    assert "qc.store(x, 3)" in code


def test_float_internal_state_uses_float_type() -> None:
    source = '''
    OPENQASM 3.0;
    float[32] theta = 1.25;
    '''

    code = _transpile_qiskit(source)

    assert "types.Float()" in code
    assert "theta = qc.add_var(expr.Var.new('theta', types.Float()), 1.25)" in code


def test_bitstring_literal_is_lowered_to_integer_value() -> None:
    source = '''
    OPENQASM 3.0;
    uint[2] x = 0b01;
    '''

    code = _transpile_qiskit(source)

    assert "x = qc.add_var(expr.Var.new('x', types.Uint(2)), 1)" in code


def test_annotation_derived_classical_output_is_exposed_in_program_outputs() -> None:
    source = '''
    OPENQASM 3.1;
    uint[8] value = 1;
    @leqo.output 0
    let out = value;
    '''

    code, namespace = _execute_qiskit(source)

    assert "program_outputs = {0: out}" in code
    assert namespace["program_outputs"][0] == namespace["out"]


def test_annotation_derived_outputs_are_sorted_by_index() -> None:
    source = '''
    OPENQASM 3.1;
    qubit[2] q;
    @leqo.output 1
    let second = q[1];
    @leqo.output 0
    let first = q[0];
    '''

    code, namespace = _execute_qiskit(source)

    assert "program_outputs = {0: first, 1: second}" in code
    assert list(namespace["program_outputs"].keys()) == [0, 1]


def test_qaoa_maxcut_3q_p1_kernel_preserves_parameterized_structure() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    input angle gamma;
    input angle beta;
    qubit[3] q;
    bit[3] c;
    h q[0];
    h q[1];
    h q[2];
    cx q[0], q[1];
    rz(gamma) q[1];
    cx q[0], q[1];
    cx q[1], q[2];
    rz(gamma) q[2];
    cx q[1], q[2];
    rx(beta) q[0];
    rx(beta) q[1];
    rx(beta) q[2];
    measure q -> c;
    '''

    code = _transpile_qiskit(source)

    assert 'Parameter("gamma")' in code or "Parameter('gamma')" in code
    assert 'Parameter("beta")' in code or "Parameter('beta')" in code
    assert code.count("qc.h(q[") == 3
    assert code.count("qc.cx(") == 4
    assert code.count("qc.rz(gamma,") == 2
    assert code.count("qc.rx(beta,") == 3
    assert "qc.measure(q, c)" in code
    assert "simulator.run" not in code


def test_qaoa_scaled_parameter_expressions_preserve_python_arithmetic() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    input angle gamma;
    input angle beta;
    qubit[2] q;
    bit[2] c;
    h q[0];
    h q[1];
    cx q[0], q[1];
    rz(2 * gamma) q[1];
    cx q[0], q[1];
    rx(2 * beta) q[0];
    rx(2 * beta) q[1];
    measure q -> c;
    '''

    code = _transpile_qiskit(source)

    assert "expr.mul" not in code
    assert "qc.rz(2 * gamma, q[1])" in code
    assert code.count("qc.rx(2 * beta,") == 2
    assert "simulator.run" not in code


def test_qaoa_maxcut_3q_p1_fixed_angles_executes() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit[3] q;
    bit[3] c;
    h q[0];
    h q[1];
    h q[2];
    cx q[0], q[1];
    rz(0.7) q[1];
    cx q[0], q[1];
    cx q[1], q[2];
    rz(0.7) q[2];
    cx q[1], q[2];
    rx(0.4) q[0];
    rx(0.4) q[1];
    rx(0.4) q[2];
    measure q -> c;
    '''

    code, namespace = _execute_qiskit(source)

    assert "qc.measure(q, c)" in code
    assert sum(namespace["counts"].values()) == 500
    assert all(len(bitstring) == 3 for bitstring in namespace["counts"])


def test_parameter_inputs_remain_external_instead_of_placeholder_bound() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    input float theta;
    qubit q;
    rx(theta) q;
    bit c = measure q;
    '''

    code = _transpile_qiskit(source)

    assert 'Parameter("theta")' in code or "Parameter('theta')" in code
    assert "assign_parameters" not in code
    assert "0.1" not in code
    assert "simulator.run" not in code


def test_vqe_hwe_2q_ansatz_preserves_parameterized_structure() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    input angle theta0;
    input angle theta1;
    input angle theta2;
    input angle theta3;
    qubit[2] q;
    bit[2] c;
    ry(theta0) q[0];
    ry(theta1) q[1];
    cx q[0], q[1];
    rz(theta2) q[0];
    rz(theta3) q[1];
    measure q -> c;
    '''

    code = _transpile_qiskit(source)

    for name in ["theta0", "theta1", "theta2", "theta3"]:
        assert f"Parameter('{name}')" in code or f'Parameter("{name}")' in code
    assert "qc.ry(theta0, q[0])" in code
    assert "qc.ry(theta1, q[1])" in code
    assert "qc.cx(q[0], q[1])" in code
    assert "qc.rz(theta2, q[0])" in code
    assert "qc.rz(theta3, q[1])" in code
    assert "qc.measure(q, c)" in code
    assert "simulator.run" not in code


def test_vqe_xx_measurement_kernel_applies_basis_rotations_before_measurement() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    input angle theta0;
    input angle theta1;
    qubit[2] q;
    bit[2] c;
    ry(theta0) q[0];
    ry(theta1) q[1];
    cx q[0], q[1];
    h q[0];
    h q[1];
    measure q -> c;
    '''

    code = _transpile_qiskit(source)

    assert "qc.ry(theta0, q[0])" in code
    assert "qc.ry(theta1, q[1])" in code
    assert "qc.cx(q[0], q[1])" in code
    assert code.count("qc.h(q[") == 2
    assert "qc.measure(q, c)" in code
    assert "simulator.run" not in code


def test_classical_add_expression_uses_qiskit_expr_arithmetic() -> None:
    source = '''
    OPENQASM 3.0;
    uint[8] value = 1;
    value = value + 2;
    '''

    code = _transpile_qiskit(source)

    assert "qc.store(value, expr.add(value, 2))" in code


def test_cast_expression_uses_python_cast_for_non_classical_domain() -> None:
    source = '''
    OPENQASM 3.0;
    float[32] theta = float[32](1);
    '''

    code = _transpile_qiskit(source)

    assert "theta = qc.add_var(expr.Var.new('theta', types.Float()), float(1))" in code


def test_array_declaration_supports_indexed_gate_arguments() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    array[angle[32], 2] beta = {0.1, 0.2};
    qubit q;
    rx(beta[1]) q;
    bit c = measure q;
    '''

    code, namespace = _execute_qiskit(source)

    assert "beta = [0.1, 0.2]" in code
    assert "qc.rx(beta[1], q)" in code
    assert sum(namespace["counts"].values()) == 500


def test_angle_input_is_parameterized_and_blocks_auto_execution() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    input angle theta;
    qubit q;
    rz(theta) q;
    bit c = measure q;
    '''

    code = _transpile_qiskit(source)

    assert 'Parameter("theta")' in code or "Parameter('theta')" in code
    assert "qc.rz(theta, q)" in code
    assert "simulator.run" not in code


def test_runtime_inputs_are_not_forced_to_zero_placeholders() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    input uint[16] x;
    qubit q;
    if (x == 1) {
        x q;
    }
    bit c = measure q;
    '''

    code = _transpile_qiskit(source)

    assert "qc.add_input('x', types.Uint(16))" in code or 'qc.add_input("x", types.Uint(16))' in code
    assert "Defaulting to 0" not in code
    assert "input_map" not in code
    assert "simulator.run" not in code


def test_input_bit_uses_uint1_type() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    input bit flag;
    qubit q;
    if (flag == 1) {
        x q;
    }
    bit c = measure q;
    '''

    code = _transpile_qiskit(source)

    assert "qc.add_input('flag', types.Uint(1))" in code or 'qc.add_input("flag", types.Uint(1))' in code
    assert "simulator.run" not in code


def test_output_declaration_uses_typed_var_and_store() -> None:
    source = '''
    OPENQASM 3.0;
    output bool result;
    input uint[16] x;
    result = x == 1;
    '''

    code = _transpile_qiskit(source)

    assert "result = expr.Var.new('result', types.Bool())" in code
    assert "qc.add_uninitialized_var(result)" in code
    assert "qc.store(result, expr.equal(" in code
    assert "AerSimulator" not in code


def test_bit_output_uses_uint1_type() -> None:
    source = '''
    OPENQASM 3.0;
    output bit result;
    result = 1;
    '''

    code = _transpile_qiskit(source)

    assert "result = expr.Var.new('result', types.Uint(1))" in code
    assert "qc.store(result, 1)" in code


def test_negative_step_for_loop_translates_to_inclusive_python_range() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit q;
    for uint i in [3:-1:0] {
        x q;
    }
    '''

    code = _transpile_qiskit(source)

    assert "with qc.for_loop(range(3, -1, -1)) as i:" in code


def test_discrete_set_for_loop_translates_to_python_list() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit q;
    for uint i in {1, 3, 5} {
        x q;
    }
    '''

    code = _transpile_qiskit(source)

    assert "with qc.for_loop([1, 3, 5]) as i:" in code


def test_compound_runtime_condition_preserves_logic_structure() -> None:
    source = '''
    OPENQASM 3.0;
    include "stdgates.inc";
    input uint[16] x;
    input uint[16] y;
    qubit q;
    if (x < 3 && (y == 0 || y > 5)) {
        x q;
    }
    bit c = measure q;
    '''

    code = _transpile_qiskit(source)

    assert "expr.logic_and(" in code
    assert "expr.logic_or(" in code
    assert "expr.less(" in code
    assert "expr.greater(" in code
    assert "simulator.run" not in code


def test_bitwise_assignment_uses_expr_bit_and() -> None:
    source = '''
    OPENQASM 3.0;
    uint[8] mask = 3;
    mask &= 1;
    '''

    code = _transpile_qiskit(source)

    assert "mask = qc.add_var(expr.Var.new('mask', types.Uint(8)), 3)" in code
    assert "qc.store(mask, expr.bit_and(mask, 1))" in code


def test_unary_not_condition_uses_logic_not() -> None:
    source = '''
    OPENQASM 3.0;
    bool flag = false;
    qubit q;
    if (!flag) {
        x q;
    }
    '''

    code = _transpile_qiskit(source)

    assert "expr.logic_not(flag)" in code


def test_alias_slice_translates_to_python_slice() -> None:
    source = '''
    OPENQASM 3.0;
    qubit[3] q;
    let tail = q[1:2];
    '''

    code = _transpile_qiskit(source)

    assert "tail = q[1:3]" in code


def test_alias_discrete_set_translates_to_python_list_of_qubits() -> None:
    source = '''
    OPENQASM 3.0;
    qubit[3] q;
    let edge = q[{0, 2}];
    '''

    code = _transpile_qiskit(source)

    assert "edge = [q[0], q[2]]" in code


def test_concatenation_alias_translates_to_python_add() -> None:
    source = '''
    OPENQASM 3.0;
    qubit[1] a;
    qubit[1] b;
    let both = a ++ b;
    '''

    code = _transpile_qiskit(source)

    assert "both = a + b" in code


def test_sub_assignment_uses_expr_sub() -> None:
    source = '''
    OPENQASM 3.0;
    uint[8] value = 5;
    value -= 2;
    '''

    code = _transpile_qiskit(source)

    assert "qc.store(value, expr.sub(value, 2))" in code


def test_bitwise_or_assignment_uses_expr_bit_or() -> None:
    source = '''
    OPENQASM 3.0;
    uint[8] value = 1;
    value |= 2;
    '''

    code = _transpile_qiskit(source)

    assert "qc.store(value, expr.bit_or(value, 2))" in code


def test_unsupported_switch_statement_fails_loudly() -> None:
    source = '''
    OPENQASM 3.0;
    uint[8] x = 1;
    switch (x) {
        case 1 {
            uint[8] y = 2;
        }
    }
    '''

    with pytest.raises(NotImplementedError, match="SwitchStatement"):
        _transpile_qiskit(source)


def test_unsupported_break_statement_fails_loudly() -> None:
    source = '''
    OPENQASM 3.0;
    while (true) {
        break;
    }
    '''

    with pytest.raises(NotImplementedError, match="BreakStatement"):
        _transpile_qiskit(source)


def test_unsupported_continue_statement_fails_loudly() -> None:
    source = '''
    OPENQASM 3.0;
    while (true) {
        continue;
    }
    '''

    with pytest.raises(NotImplementedError, match="ContinueStatement"):
        _transpile_qiskit(source)


def test_non_bit_measurement_initializer_fails_loudly() -> None:
    source = '''
    OPENQASM 3.0;
    qubit q;
    bool flag = measure q;
    '''

    with pytest.raises(NotImplementedError, match="Measurement initializers are only supported for bit declarations"):
        _transpile_qiskit(source)


def test_array_input_fails_loudly() -> None:
    source = '''
    OPENQASM 3.0;
    input array[uint[8], 2] beta;
    '''

    with pytest.raises(NotImplementedError, match="Array inputs and outputs are not part of the supported executable subset"):
        _transpile_qiskit(source)


def test_array_output_fails_loudly() -> None:
    source = '''
    OPENQASM 3.0;
    output array[uint[8], 2] beta;
    '''

    with pytest.raises(NotImplementedError, match="Array inputs and outputs are not part of the supported executable subset"):
        _transpile_qiskit(source)


def test_for_loop_over_array_expression_fails_loudly() -> None:
    source = '''
    OPENQASM 3.0;
    array[angle[32], 2] beta = {0.1, 0.2};
    qubit q;
    for uint i in beta {
        rx(i) q;
    }
    '''

    with pytest.raises(NotImplementedError, match="For-in loops are only supported over ranges and discrete sets"):
        _transpile_qiskit(source)


def test_signed_integer_internal_state_fails_loudly() -> None:
    source = '''
    OPENQASM 3.0;
    int[8] value = 1;
    '''

    with pytest.raises(NotImplementedError, match="Signed OpenQASM int"):
        _transpile_qiskit(source)


def test_signed_integer_runtime_input_fails_loudly() -> None:
    source = '''
    OPENQASM 3.0;
    input int[16] x;
    '''

    with pytest.raises(NotImplementedError, match="Signed OpenQASM int"):
        _transpile_qiskit(source)


def test_signed_integer_cast_fails_loudly() -> None:
    source = '''
    OPENQASM 3.0;
    uint[8] value = 1;
    float[32] theta = 0.0;
    theta = int[8](value);
    '''

    with pytest.raises(NotImplementedError, match="Signed OpenQASM int"):
        _transpile_qiskit(source)

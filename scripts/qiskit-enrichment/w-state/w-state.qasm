OPENQASM 3.1;
include "stdgates.inc";
qubit[3] leqo_reg;
/* Start node prepare */
gate leqo_aa3a7f547f5f5337872930f6b38a8308_unitary _gate_q_0 {
  U(1.230959417340775, 0, 0) _gate_q_0;
}
gate leqo_aa3a7f547f5f5337872930f6b38a8308_multiplexer_dg _gate_q_0 {
  leqo_aa3a7f547f5f5337872930f6b38a8308_unitary _gate_q_0;
}
gate leqo_aa3a7f547f5f5337872930f6b38a8308_unitary_0 _gate_q_0 {
  U(pi / 2, -7 * pi / 4, 0) _gate_q_0;
}
gate leqo_aa3a7f547f5f5337872930f6b38a8308_unitary_1 _gate_q_0 {
  U(pi / 2, pi / 2, -3 * pi / 4) _gate_q_0;
}
gate leqo_aa3a7f547f5f5337872930f6b38a8308_multiplexer_dg_0 _gate_q_0, _gate_q_1 {
  leqo_aa3a7f547f5f5337872930f6b38a8308_unitary_0 _gate_q_0;
  cx _gate_q_1, _gate_q_0;
  leqo_aa3a7f547f5f5337872930f6b38a8308_unitary_1 _gate_q_0;
}
gate leqo_aa3a7f547f5f5337872930f6b38a8308_unitary_2 _gate_q_0 {
  U(pi / 2, pi / 4, pi) _gate_q_0;
}
gate leqo_aa3a7f547f5f5337872930f6b38a8308_unitary_3 _gate_q_0 {
  U(pi / 4, -pi / 2, 3 * pi / 4) _gate_q_0;
}
gate leqo_aa3a7f547f5f5337872930f6b38a8308_unitary_4 _gate_q_0 {
  U(pi / 4, -5 * pi / 4, -pi / 2) _gate_q_0;
}
gate leqo_aa3a7f547f5f5337872930f6b38a8308_unitary_5 _gate_q_0 {
  U(pi / 2, -3 * pi / 2, 5 * pi / 4) _gate_q_0;
}
gate leqo_aa3a7f547f5f5337872930f6b38a8308_multiplexer_dg_1 _gate_q_0, _gate_q_1, _gate_q_2 {
  leqo_aa3a7f547f5f5337872930f6b38a8308_unitary_2 _gate_q_0;
  cx _gate_q_1, _gate_q_0;
  leqo_aa3a7f547f5f5337872930f6b38a8308_unitary_3 _gate_q_0;
  cx _gate_q_2, _gate_q_0;
  leqo_aa3a7f547f5f5337872930f6b38a8308_unitary_4 _gate_q_0;
  cx _gate_q_1, _gate_q_0;
  leqo_aa3a7f547f5f5337872930f6b38a8308_unitary_5 _gate_q_0;
}
gate leqo_aa3a7f547f5f5337872930f6b38a8308_isometry_to_uncompute_dg _gate_q_0, _gate_q_1, _gate_q_2 {     
  leqo_aa3a7f547f5f5337872930f6b38a8308_multiplexer_dg _gate_q_2;
  leqo_aa3a7f547f5f5337872930f6b38a8308_multiplexer_dg_0 _gate_q_1, _gate_q_2;
  leqo_aa3a7f547f5f5337872930f6b38a8308_multiplexer_dg_1 _gate_q_0, _gate_q_1, _gate_q_2;
}
gate leqo_aa3a7f547f5f5337872930f6b38a8308_state_preparation(_gate_p_0, _gate_p_1, _gate_p_2, _gate_p_3, _gate_p_4, _gate_p_5, _gate_p_6, _gate_p_7) _gate_q_0, _gate_q_1, _gate_q_2 {
  leqo_aa3a7f547f5f5337872930f6b38a8308_isometry_to_uncompute_dg _gate_q_0, _gate_q_1, _gate_q_2;
}
let leqo_aa3a7f547f5f5337872930f6b38a8308_state = leqo_reg[{0, 1, 2}];
leqo_aa3a7f547f5f5337872930f6b38a8308_state_preparation(0, 0.5773502691896258, 0.5773502691896258, 0, 0.5773502691896258, 0, 0, 0) leqo_aa3a7f547f5f5337872930f6b38a8308_state[0], leqo_aa3a7f547f5f5337872930f6b38a8308_state[1], leqo_aa3a7f547f5f5337872930f6b38a8308_state[2];
@leqo.output 0
let leqo_aa3a7f547f5f5337872930f6b38a8308_state_out = leqo_aa3a7f547f5f5337872930f6b38a8308_state;        
/* End node prepare */
/* Start node measure */
@leqo.input 0
let leqo_4983cc78a037571ca3ca46051929624b_q = leqo_reg[{0, 1, 2}];
bit[3] leqo_4983cc78a037571ca3ca46051929624b_result = measure leqo_4983cc78a037571ca3ca46051929624b_q[{0, 1, 2}];
@leqo.output 0
let leqo_4983cc78a037571ca3ca46051929624b_out = leqo_4983cc78a037571ca3ca46051929624b_result;
@leqo.output 1
let leqo_4983cc78a037571ca3ca46051929624b_qubit_out = leqo_4983cc78a037571ca3ca46051929624b_q;
/* End node measure */
OPENQASM 3.0;
include "stdgates.inc";

input float[64] theta;
qubit[1] q;
bit[1] out;

rx(theta) q[0];
out[0] = measure q[0];

OPENQASM 3.0;
include "stdgates.inc";

uint[32] counter = 0;
qubit[1] q;
bit[1] out;

x q[0];
out[0] = measure q[0];

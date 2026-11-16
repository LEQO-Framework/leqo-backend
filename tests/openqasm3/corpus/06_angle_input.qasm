OPENQASM 3.0;
include "stdgates.inc";

input angle[64] phi;
qubit[1] q;
bit[1] out;

rz(phi) q[0];
out[0] = measure q[0];

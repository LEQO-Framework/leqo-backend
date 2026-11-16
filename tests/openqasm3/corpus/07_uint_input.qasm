OPENQASM 3.0;
include "stdgates.inc";

input uint[32] n;
qubit[1] q;
bit[1] out;

x q[0];
out[0] = measure q[0];

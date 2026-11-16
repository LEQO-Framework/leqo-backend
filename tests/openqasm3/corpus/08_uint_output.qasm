OPENQASM 3.0;
include "stdgates.inc";

output uint[32] r;
qubit[1] q;
bit[1] out;

x q[0];
out[0] = measure q[0];
r = 7;

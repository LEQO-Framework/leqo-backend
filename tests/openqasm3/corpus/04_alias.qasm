OPENQASM 3.0;
include "stdgates.inc";

qubit[3] q;
bit[1] out;

let pair = q[{0, 2}];

h pair[0];
cx pair[0], pair[1];

out[0] = measure pair[1];

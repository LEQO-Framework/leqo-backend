OPENQASM 3.0;
include "stdgates.inc";

qubit[2] a;
qubit[2] b;
bit[1] out;

let joined = a ++ b;

h joined[0];
cx joined[0], joined[3];

out[0] = measure joined[3];

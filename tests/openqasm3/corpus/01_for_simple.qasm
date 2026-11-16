OPENQASM 3.0;
include "stdgates.inc";

qubit[1] q;
bit[1] out;

for int i in [0:1:3] {
  x q[0];
}

out[0] = measure q[0];

OPENQASM 3.0;
include "stdgates.inc";

qubit[1] q;
bit[1] c;
bit[1] out;

x q[0];
c[0] = measure q[0];

while (c[0]) {
  x q[0];
  c[0] = measure q[0];
}

out[0] = measure q[0];

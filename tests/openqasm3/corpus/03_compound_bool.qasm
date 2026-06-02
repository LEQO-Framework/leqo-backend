OPENQASM 3.0;
include "stdgates.inc";

qubit[2] q;
bit[2] c;
bit[1] out;

c[0] = measure q[0];
c[1] = measure q[1];

if (c[0] == 0 && c[1] == 0) {
  x q[0];
} else {
  z q[0];
}

out[0] = measure q[0];

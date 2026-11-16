OPENQASM 3.0;
include "stdgates.inc";

bool flag = true;
qubit[1] q;
bit[1] out;

if (flag) {
  x q[0];
}
out[0] = measure q[0];

"""
Helper script to generate expected Qiskit output for baseline tests.
Uses the transpiler directly to bypass the need for a database.

Run with: uv run python scripts/generate_qiskit_baselines.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openqasm3
from app.openqasm3.qiskit_generator import QasmToQiskitTranspiler


# These are representative QASM outputs that the pipeline produces for each test scenario.
# We feed them directly into the transpiler to get the Qiskit output.

QASM_SOURCES = {
    "basic_gates": """\
OPENQASM 3.1;
include "stdgates.inc";
qubit[1] leqo_reg;
let q0 = leqo_reg[{0}];
h q0;
let q0_after_h = q0;
x q0_after_h;
let q0_after_x = q0_after_h;
bit[1] result = measure q0_after_x[{0}];
""",

    "parameterized_gates": """\
OPENQASM 3.1;
include "stdgates.inc";
qubit[1] leqo_reg;
let q0 = leqo_reg[{0}];
rx(0.5) q0;
let q0_after_rx = q0;
rz(1.2) q0_after_rx;
""",

    "if_else": """\
OPENQASM 3.1;
include "stdgates.inc";
qubit[1] leqo_reg;
let q0 = leqo_reg[{0}];
h q0;
let q0_after_h = q0;
bit[1] result = measure q0_after_h[{0}];
let q0_after_measure = q0_after_h;
if (result == 1) {
  x q0_after_measure;
}
""",

    "for_loop": """\
OPENQASM 3.1;
include "stdgates.inc";
qubit[1] leqo_reg;
let q0 = leqo_reg[{0}];
for int i in [0:3] {
  h q0;
}
""",

    "while_loop": """\
OPENQASM 3.1;
include "stdgates.inc";
qubit[1] leqo_reg;
int[32] counter = 0;
let q0 = leqo_reg[{0}];
while (counter < 5) {
  x q0;
}
""",
}


def main():
    for name, qasm_source in QASM_SOURCES.items():
        print(f"\n{'='*60}")
        print(f"Test: {name}")
        print(f"{'='*60}")

        try:
            ast_node = openqasm3.parse(qasm_source)
            transpiler = QasmToQiskitTranspiler()
            result = transpiler.visit(ast_node)
            print(result)
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

        print(f"{'='*60}")


if __name__ == "__main__":
    main()



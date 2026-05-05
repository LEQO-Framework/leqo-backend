"""
Helper script to generate expected Qiskit output for baseline tests.

Uses the production AST-based transpiler (UniversalTranspiler + QiskitProvider)
directly, so the generated text matches what the backend pipeline produces for
``compilation_target == "qiskit"``.

Run with: uv run python scripts/generate_qiskit_baselines.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openqasm3.parser import parse

from app.openqasm3.qiskit_provider import QiskitProvider
from app.openqasm3.universal_transpiler import UniversalTranspiler


# Representative QASM outputs that the pipeline produces for each test scenario.
# Fed directly into the transpiler to obtain the Qiskit output.
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
for uint i in [0:3] {
  h q0;
}
""",

    "while_loop": """\
OPENQASM 3.1;
include "stdgates.inc";
qubit[1] leqo_reg;
uint[32] counter = 0;
let q0 = leqo_reg[{0}];
while (counter < 5) {
  x q0;
  counter += 1;
}
""",
}


def _transpile(qasm_source: str) -> str:
    program = parse(qasm_source)
    transpiler = UniversalTranspiler(QiskitProvider())
    return transpiler.visit_Program(program)


def main() -> None:
    for name, qasm_source in QASM_SOURCES.items():
        print(f"\n{'=' * 60}")
        print(f"Test: {name}")
        print(f"{'=' * 60}")

        try:
            print(_transpile(qasm_source))
        except Exception as exc:
            print(f"ERROR: {exc}")
            import traceback
            traceback.print_exc()

        print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

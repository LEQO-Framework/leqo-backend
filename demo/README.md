# Defense demo

`defense_demo.ipynb` shows the backend producing executable Qiskit and running it on
Aer, with one example also run on real IBM hardware. It uses the same
`UniversalTranspiler` and `QiskitProvider` path as `compilation_target = "qiskit"`.

Three sections:

1. Teleportation, end to end. A node-and-edge model graph runs through the full
   backend pipeline to Qiskit. Mid-circuit measurements drive `qc.if_test`
   feed-forward and the destination qubit reproduces the input state. The same
   circuit is optionally submitted to a real IBM backend, and the saved result is
   reloaded so Run All never re-queues.
2. QAOA. A MaxCut kernel on a three-node path graph, lowered from OpenQASM 3 by the
   exporter, concentrates on the optima `010` and `101`.
3. Error correction. A three-qubit bit-flip code, also from OpenQASM 3, recovers the
   flipped qubit in-circuit through measurement-driven control.

Each section shows the generated Qiskit source, the circuit, and the measured result
on Aer.

## Run

In the environment that already has the backend dependencies:

    pip install -r demo/requirements-demo.txt

Open `defense_demo.ipynb` in VS Code, select that environment as the kernel, and Run
All. The notebook walks up to the repo root, so it runs from anywhere inside the
repo. `SUBMIT_LIVE` is `False` by default, so nothing is queued and the saved
hardware result is shown. The real-hardware cell needs an IBM account saved locally
via `QiskitRuntimeService`.

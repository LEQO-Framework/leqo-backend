"""
Host-side QAOA proof of concept for thesis Section 6.5.

The script exports a parameterized p=1 QAOA kernel for MaxCut on a three-node
path graph through the same UniversalTranspiler + QiskitProvider path used by
``compilation_target == "qiskit"``. It then performs a coarse grid search over
the cost angle ``gamma`` and the mixer angle ``beta``, binds the optimum into
the exported circuit, executes the bound circuit on the Aer simulator, and
reports the resulting metrics.

Run with: uv run python scripts/qaoa_host_side_poc.py
"""

from __future__ import annotations

import os
import sys
from io import StringIO
from contextlib import redirect_stdout
from typing import Any

import numpy as np
from openqasm3.parser import parse
from qiskit.quantum_info import Statevector

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.openqasm3.qiskit_provider import QiskitProvider
from app.openqasm3.universal_transpiler import UniversalTranspiler

QASM_KERNEL = """
OPENQASM 3.0;
include "stdgates.inc";
input angle gamma;
input angle beta;
qubit[3] q;
bit[3] c;
h q[0];
h q[1];
h q[2];
cx q[0], q[1];
rz(gamma) q[1];
cx q[0], q[1];
cx q[1], q[2];
rz(gamma) q[2];
cx q[1], q[2];
rx(beta) q[0];
rx(beta) q[1];
rx(beta) q[2];
measure q -> c;
"""

# MaxCut path graph: edges (0,1) and (1,2).
EDGES: tuple[tuple[int, int], ...] = ((0, 1), (1, 2))


def cut_value(bitstring: str) -> int:
    """Number of edges whose endpoints differ in the bitstring (Qiskit endianness)."""
    bits = [int(c) for c in bitstring[::-1]]
    return sum(bits[i] != bits[j] for i, j in EDGES)


def export_circuit() -> Any:
    """Run the production exporter on the QASM kernel and return the live circuit object."""
    code = UniversalTranspiler(QiskitProvider()).visit_Program(parse(QASM_KERNEL))
    namespace: dict[str, Any] = {}
    with redirect_stdout(StringIO()):
        exec(code, namespace, namespace)
    return namespace["qc"]


def _bind(qc: Any, gamma_val: float, beta_val: float) -> Any:
    bindings = {
        param: (gamma_val if param.name == "gamma" else beta_val)
        for param in qc.parameters
    }
    return qc.assign_parameters(bindings)


def _expected_cut_from_statevector(qc: Any, gamma_val: float, beta_val: float) -> float:
    bound = _bind(qc, gamma_val, beta_val)
    bound = bound.remove_final_measurements(inplace=False)
    state = Statevector.from_instruction(bound)
    probabilities = state.probabilities_dict()
    return float(sum(prob * cut_value(bs) for bs, prob in probabilities.items()))


def run_poc(
    gamma_steps: int = 41,
    beta_steps: int = 21,
    shots: int = 4000,
    seed: int = 42,
) -> dict[str, Any]:
    """Execute the host-side workflow and return reproducible metrics."""
    from qiskit_aer import AerSimulator

    qc = export_circuit()

    gammas = np.linspace(0.0, 2.0 * np.pi, gamma_steps)
    betas = np.linspace(0.0, np.pi, beta_steps)

    best_expected = float("-inf")
    best_params: tuple[float, float] = (0.0, 0.0)
    for gamma_val in gammas:
        for beta_val in betas:
            expectation = _expected_cut_from_statevector(qc, float(gamma_val), float(beta_val))
            if expectation > best_expected:
                best_expected = expectation
                best_params = (float(gamma_val), float(beta_val))

    bound = _bind(qc, best_params[0], best_params[1])
    simulator = AerSimulator(seed_simulator=seed)
    counts = simulator.run(bound, shots=shots).result().get_counts()

    total_shots = sum(counts.values())
    optimum_keys = {"010", "101"}
    optimum_mass = sum(counts.get(key, 0) for key in optimum_keys) / total_shots
    sampled_expectation = sum(
        (count / total_shots) * cut_value(bs) for bs, count in counts.items()
    )
    dominant = [bs for bs, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:2]]

    return {
        "best_expected_cut": best_expected,
        "best_params": best_params,
        "optimum_mass": optimum_mass,
        "sampled_expected_cut": sampled_expectation,
        "dominant": dominant,
        "counts": counts,
    }


def _format_metrics(metrics: dict[str, Any]) -> str:
    return (
        f"Best expected cut value:                      {metrics['best_expected_cut']:.3f}\n"
        f"Best (gamma, beta):                           "
        f"({metrics['best_params'][0]:.4f}, {metrics['best_params'][1]:.4f})\n"
        f"Probability mass on optimal cuts (010, 101):  {metrics['optimum_mass']:.3f}\n"
        f"Sampled expected cut after binding:           {metrics['sampled_expected_cut']:.3f}\n"
        f"Dominant sampled bitstrings:                  {', '.join(metrics['dominant'])}"
    )


if __name__ == "__main__":
    print(_format_metrics(run_poc()))

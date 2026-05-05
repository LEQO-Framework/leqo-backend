"""Reproducible regression for the host-side QAOA proof of concept (Section 6.5)."""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from scripts.qaoa_host_side_poc import run_poc


def test_qaoa_host_side_poc_metrics_match_chapter_table() -> None:
    metrics = run_poc(gamma_steps=41, beta_steps=21, shots=4000, seed=42)

    # Best expected cut clearly exceeds the random-assignment baseline of 1.0
    # for the two-edge path graph.
    assert metrics["best_expected_cut"] > 1.5

    # Optimized kernel concentrates strongly on the two MaxCut bitstrings.
    assert metrics["optimum_mass"] > 0.6

    # Sampled estimate is consistent with the optimized kernel within the
    # standard-error band for 4000 shots (sigma ~ 0.015 for a bounded value).
    assert abs(metrics["sampled_expected_cut"] - metrics["best_expected_cut"]) < 0.1

    # The optima dominate the sampling distribution.
    assert set(metrics["dominant"]) == {"010", "101"}

    # Counts cover only valid 3-bit strings.
    assert all(len(bs) == 3 for bs in metrics["counts"])
    assert sum(metrics["counts"].values()) == 4000

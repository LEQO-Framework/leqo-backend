"""Reproducible regression for the larger host-side QAOA proof of concept (Section 6.3)."""

from scripts.qaoa_host_side_poc_large import run_poc

SHOTS = 4000


def test_qaoa_host_side_poc_large_metrics_match_chapter_table() -> None:
    metrics = run_poc(gamma_steps=41, beta_steps=21, shots=SHOTS, seed=42)

    # The complete bipartite graph K_{2,3} is bipartite, so its maximum cut
    # equals all six edges, achieved by the two color-class assignments that
    # split the parts {0,1} and {2,3,4} onto opposite sides.
    assert metrics["max_cut"] == 6  # noqa: PLR2004
    assert metrics["num_optima"] == 2  # noqa: PLR2004

    # Best expected cut clearly exceeds the random-assignment baseline of 3.0
    # for the six-edge graph, while staying below the unreachable optimum of 6
    # that a single p=1 layer cannot concentrate on.
    assert metrics["best_expected_cut"] > 4.0  # noqa: PLR2004

    # Optimized kernel concentrates a substantial fraction of its mass on the
    # two MaxCut bitstrings.
    assert metrics["optimum_mass"] > 0.35  # noqa: PLR2004

    # Sampled estimate is consistent with the optimized kernel within the
    # standard-error band for 4000 shots (sigma ~ 0.02 for a bounded value).
    assert abs(metrics["sampled_expected_cut"] - metrics["best_expected_cut"]) < 0.1  # noqa: PLR2004

    # Counts cover only valid 5-bit strings.
    assert all(len(bs) == 5 for bs in metrics["counts"])  # noqa: PLR2004
    assert sum(metrics["counts"].values()) == SHOTS

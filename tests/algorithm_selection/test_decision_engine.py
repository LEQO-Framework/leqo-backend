import uuid
from datetime import UTC, datetime

import pytest

from app.algorithm_selection.decision_engine import (
    AlgorithmDecisionEngine,
    DecisionSettings,
    default_candidate,
)
from app.algorithm_selection.models import (
    Candidate,
    CandidateEvaluation,
    QPUSelection,
    QuantumAlgorithm,
    QUBOProblem,
)
from app.algorithm_selection.repository import SimilarRecord
from app.model.database_model import ExecutionRecord

QAOA1 = Candidate(algorithm=QuantumAlgorithm.QAOA, layers=1)
QAOA2 = Candidate(algorithm=QuantumAlgorithm.QAOA, layers=2)
VQE1 = Candidate(algorithm=QuantumAlgorithm.VQE, layers=1)
VQE2 = Candidate(algorithm=QuantumAlgorithm.VQE, layers=2)


def chain(n: int) -> QUBOProblem:
    """
    Maximum independent set on a chain of ``n`` variables: strong local fields.
    """
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        matrix[i][i] = -1
        if i + 1 < n:
            matrix[i][i + 1] = 2
    return QUBOProblem(matrix=matrix)


def maxcut(n: int, edges: list[tuple[int, int]]) -> QUBOProblem:
    """
    MaxCut ``min sum -(x_i + x_j - 2 x_i x_j)``: no local fields.
    """
    matrix = [[0.0] * n for _ in range(n)]
    for i, j in edges:
        matrix[i][i] -= 1
        matrix[j][j] -= 1
        matrix[i][j] += 2
    return QUBOProblem(matrix=matrix)


QUBO = chain(3)
UNDECIDED = chain(15)
LARGE = chain(18)
WEAK_FIELD = maxcut(16, [(i, i + 1) for i in range(15)])
DENSE_WEAK_FIELD = maxcut(16, [(i, j) for i in range(16) for j in range(i + 1, 16)])

ENGINE = AlgorithmDecisionEngine(DecisionSettings())
RULE_ONLY = AlgorithmDecisionEngine(DecisionSettings(weight_history=0))
HISTORY_ONLY = AlgorithmDecisionEngine(DecisionSettings(weight_problem_structure=0))
RULE = "Problem structure rule"


def selection(error_chance: float | None) -> QPUSelection:
    return QPUSelection(
        provider="ibmq",
        qpu="ibmq_hanoi",
        compiler="qiskit",
        mcda_method="topsis",
        mcda_position=2,
        mcda_score=0.5,
        analyzed_depth=10,
        analyzed_width=3,
        number_of_single_qubit_gates=10,
        number_of_multi_qubit_gates=4,
        number_of_measurement_operations=3,
        avg_single_qubit_gate_error=0.001,
        avg_multi_qubit_gate_error=0.01,
        avg_readout_error=0.02,
        t1=50000.0,
        t2=50000.0,
        transpiled_circuit=None,
        estimated_success_probability=None
        if error_chance is None
        else 1 - error_chance,
        error_chance=error_chance,
    )


def evaluation(
    candidate: Candidate,
    error_chance: float | None = None,
    *,
    reachable: bool = True,
) -> CandidateEvaluation:
    has_qpu = reachable and error_chance is not None
    return CandidateEvaluation(
        algorithm=candidate.algorithm,
        layers=candidate.layers,
        qasm="OPENQASM 2.0;",
        width=3,
        qpu_selection=selection(error_chance) if has_qpu else None,
        nisq_reachable=reachable,
        nisq_error=None if has_qpu else "no QPU" if reachable else "unreachable",
    )


def unreachable(*candidates: Candidate) -> list[CandidateEvaluation]:
    return [evaluation(c, reachable=False) for c in candidates]


def similar(
    qualities: dict[Candidate, float], similarity: float = 1.0
) -> SimilarRecord:
    record = ExecutionRecord(
        id=uuid.uuid4(),
        created_at=datetime.now(UTC),
        input_qubo={},
        num_variables=3,
        density=2 / 3,
        variable_names=["x0", "x1", "x2"],
        selected_algorithm="VQE",
        selected_layers=1,
        generated_qasm="",
        reasoning="",
        candidate_evaluations=[],
        succeeded=True,
        candidate_qualities={str(c): q for c, q in qualities.items()},
    )
    return SimilarRecord(record, similarity)


def test_candidate_labels() -> None:
    assert str(QAOA2) == "QAOA p=2"
    assert str(VQE1) == "VQE L=1"
    assert VQE1.model_dump() == {"algorithm": "VQE", "layers": 1, "label": "VQE L=1"}


def test_default_is_the_shallowest_vqe() -> None:
    assert default_candidate([VQE2, QAOA1, VQE1]) == VQE1
    assert default_candidate([QAOA2, QAOA1]) == QAOA1


def test_field_coupling_ratio_of_the_ising_form() -> None:
    assert WEAK_FIELD.field_coupling_ratio == pytest.approx(0)
    # J = 1/2 per coupling, h = 0 at the ends and -1/2 inside the chain.
    assert chain(16).field_coupling_ratio == pytest.approx((14 * 0.5 / 16) / 0.5)


def test_nisq_filter_removes_candidates_without_qpu_or_with_high_error_chance() -> None:
    decision = RULE_ONLY.decide(
        LARGE,
        [
            evaluation(QAOA1, 0.35),
            evaluation(QAOA2),
            evaluation(VQE1, 0.20),
            evaluation(VQE2, 0.60),
        ],
        [],
    )

    assert set(decision.excluded) == {QAOA2, VQE2}
    assert decision.excluded[QAOA2] == "no QPU"
    assert "error chance 0.600 on ibmq_hanoi exceeds 0.5" in decision.excluded[VQE2]
    assert set(decision.scores) == {QAOA1, VQE1}
    # A feasible QAOA is not rejected just because VQE has the lower error chance.
    assert decision.candidate == QAOA1
    assert not decision.fallback_used


def test_nisq_filter_keeps_candidates_without_error_chance() -> None:
    decision = RULE_ONLY.decide(LARGE, unreachable(QAOA1, QAOA2, VQE1), [])

    assert decision.excluded == {}
    # Without error chances, the deepest QAOA.
    assert decision.candidate == QAOA2


def test_no_feasible_candidate_falls_back_to_executable_vqe() -> None:
    decision = ENGINE.decide(
        LARGE, [evaluation(QAOA1, 0.9), evaluation(VQE2, 0.8), evaluation(VQE1)], []
    )

    assert decision.candidate == VQE2
    assert decision.fallback_used
    assert "No candidate is feasible" in decision.reasoning


ALL_FEASIBLE = [
    evaluation(QAOA1, 0.30),
    evaluation(QAOA2, 0.40),
    evaluation(VQE1, 0.35),
    evaluation(VQE2, 0.25),
]


@pytest.mark.parametrize(
    ("qubo", "expected"),
    [
        (chain(14), VQE2),
        (LARGE, QAOA2),
        (WEAK_FIELD, QAOA2),
        (chain(16), VQE2),
        (DENSE_WEAK_FIELD, VQE2),
    ],
    ids=["small", "large", "weak field", "strong field", "dense"],
)
def test_structure_rule_picks_algorithm_by_size_field_and_density(
    qubo: QUBOProblem, expected: Candidate
) -> None:
    decision = RULE_ONLY.decide(qubo, ALL_FEASIBLE, [])
    rule = next(s for s in decision.signals if s.name == RULE)

    # QAOA: the deepest feasible one; VQE: the one with the lowest error chance.
    assert rule.preferred == expected
    assert decision.candidate == expected


def test_structure_rule_explains_field_and_density() -> None:
    decision = RULE_ONLY.decide(chain(16), ALL_FEASIBLE, [])
    rule = next(s for s in decision.signals if s.name == RULE)

    assert (
        "16 variables with field/coupling ratio 0.88 (limit 0.78) and density 0.12 "
        "(limit 0.625) favour VQE" in rule.explanation
    )


def test_structure_rule_needs_a_reliable_qaoa_candidate() -> None:
    decision = RULE_ONLY.decide(
        LARGE,
        [evaluation(QAOA1, 0.45), evaluation(QAOA2, 0.48), evaluation(VQE1, 0.35)],
        [],
    )
    rule = next(s for s in decision.signals if s.name == RULE)

    assert rule.preferred == VQE1
    assert "no QAOA candidate has an error chance of at most 0.4" in rule.explanation


def test_structure_rule_skips_qaoa_above_the_error_limit() -> None:
    decision = RULE_ONLY.decide(
        LARGE,
        [evaluation(QAOA1, 0.30), evaluation(QAOA2, 0.48), evaluation(VQE1, 0.35)],
        [],
    )
    rule = next(s for s in decision.signals if s.name == RULE)

    # QAOA p=2 is feasible (error chance at most 0.5) but above the rule's limit of 0.4.
    assert rule.preferred == QAOA1
    assert decision.candidate == QAOA1


def test_structure_rule_does_not_vote_between_the_limits() -> None:
    decision = RULE_ONLY.decide(
        UNDECIDED, [evaluation(QAOA1, 0.3), evaluation(VQE2, 0.3)], []
    )
    rule = next(s for s in decision.signals if s.name == RULE)

    assert rule.preferred is None
    assert "15 variables lie between 14 and 16" in rule.explanation
    assert decision.candidate == VQE2
    assert decision.fallback_used


def test_structure_rule_uses_configured_limits() -> None:
    engine = AlgorithmDecisionEngine(
        DecisionSettings(
            weight_history=0,
            vqe_max_variables=1,
            qaoa_min_variables=2,
            qaoa_always_variables=3,
        )
    )
    decision = engine.decide(QUBO, [evaluation(QAOA1, 0.3), evaluation(VQE1, 0.3)], [])

    assert decision.candidate == QAOA1
    assert "3 variables (at least 3) favour QAOA" in decision.reasoning


def test_structure_rule_limits_must_be_ordered() -> None:
    with pytest.raises(ValueError, match="must be larger"):
        DecisionSettings(vqe_max_variables=16, qaoa_min_variables=16)
    with pytest.raises(ValueError, match="must not be smaller"):
        DecisionSettings(qaoa_min_variables=16, qaoa_always_variables=15)


def test_structure_rule_skips_infeasible_candidates() -> None:
    decision = RULE_ONLY.decide(QUBO, [evaluation(QAOA1, 0.2), evaluation(VQE1)], [])
    rule = next(s for s in decision.signals if s.name == RULE)

    assert rule.preferred is None
    assert "no VQE candidate is feasible" in rule.explanation


def test_history_prefers_best_mean_quality() -> None:
    decision = HISTORY_ONLY.decide(
        QUBO,
        unreachable(QAOA1, VQE1, VQE2),
        [
            similar({QAOA1: 0.80, VQE1: 0.90, VQE2: 0.95}, similarity=1.0),
            similar({QAOA1: 0.70, VQE1: 0.92, VQE2: 0.85}, similarity=0.5),
        ],
    )
    history = next(s for s in decision.signals if s.name == "History")

    # Similarity-weighted means: VQE L=1 (0.9 + 0.46) / 1.5 = 0.907, VQE L=2 0.917.
    assert history.preferred == VQE2
    assert decision.candidate == VQE2
    assert not decision.fallback_used
    assert (
        "VQE L=2 has the best mean quality on 2 similar QUBO(s)" in decision.reasoning
    )


def test_history_abstains_without_a_clear_lead() -> None:
    # On a large weak-field QUBO the structure rule votes for QAOA.
    decision = ENGINE.decide(
        WEAK_FIELD,
        [evaluation(QAOA2, 0.30), evaluation(VQE1, 0.20)],
        [similar({QAOA2: 0.896, VQE1: 0.900})],
    )
    history = next(s for s in decision.signals if s.name == "History")

    assert history.preferred is None
    assert "VQE L=1 leads by only 0.004 (margin 0.005)" in history.explanation
    assert decision.candidate == QAOA2


def test_history_only_votes_for_feasible_candidates() -> None:
    decision = HISTORY_ONLY.decide(
        QUBO,
        [evaluation(QAOA2), evaluation(VQE1, 0.2)],
        [similar({QAOA2: 0.99, VQE1: 0.80})],
    )

    assert decision.candidate == VQE1
    assert QAOA2 in decision.excluded


def test_history_without_qualities_abstains() -> None:
    decision = HISTORY_ONLY.decide(QUBO, unreachable(QAOA1, VQE1), [similar({})])
    history = next(s for s in decision.signals if s.name == "History")

    assert history.preferred is None
    assert decision.candidate == VQE1
    assert decision.fallback_used


def test_history_outweighs_structure_rule() -> None:
    # History (0.6) prefers VQE L=1 on a large QUBO, the structure rule (0.4) QAOA p=1.
    decision = ENGINE.decide(
        LARGE,
        [evaluation(QAOA1, 0.30), evaluation(VQE1, 0.20)],
        [similar({QAOA1: 0.70, VQE1: 0.90})],
    )

    assert decision.candidate == VQE1
    assert decision.scores == {QAOA1: pytest.approx(0.4), VQE1: pytest.approx(0.6)}


def test_agreeing_signals_add_up() -> None:
    decision = ENGINE.decide(
        LARGE,
        [evaluation(QAOA1, 0.30), evaluation(VQE1, 0.20)],
        [similar({QAOA1: 0.95, VQE1: 0.90})],
    )

    assert decision.candidate == QAOA1
    assert decision.scores == {QAOA1: pytest.approx(1.0), VQE1: pytest.approx(0.0)}


def test_equal_weights_with_disagreeing_signals_fall_back() -> None:
    engine = AlgorithmDecisionEngine(
        DecisionSettings(weight_history=0.5, weight_problem_structure=0.5)
    )
    decision = engine.decide(
        LARGE,
        [evaluation(QAOA1, 0.30), evaluation(VQE2, 0.30), evaluation(VQE1, 0.40)],
        [similar({QAOA1: 0.70, VQE2: 0.90})],
    )

    assert decision.candidate == VQE1
    assert decision.fallback_used

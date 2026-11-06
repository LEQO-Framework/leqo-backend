"""
Decide which candidate (algorithm and circuit depth) solves a QUBO.

The NISQ Analyzer decides which candidates are feasible: a candidate is removed if no QPU can
execute its circuit or if the error chance of its top-ranked QPU exceeds ``max_error_chance``.
Among the remaining candidates, each signal votes for at most one candidate with its weight:

* History: the candidate with the best similarity-weighted mean solution quality for similar QUBOs.
* Problem structure rule: VQE for small QUBOs, QAOA for large ones; in between QAOA only for
  QUBOs with weak local fields and a limited density. It only votes for QAOA if a feasible QAOA
  candidate has an error chance of at most ``qaoa_max_error_chance``.

The candidate with the strictly highest score wins.
Without a clear winner, the shallowest feasible VQE is selected.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

from app.algorithm_selection.models import (
    Candidate,
    CandidateEvaluation,
    QuantumAlgorithm,
    QUBOProblem,
    SignalResult,
)
from app.algorithm_selection.repository import SimilarRecord

DEFAULT_ALGORITHM = QuantumAlgorithm.VQE


@dataclass(frozen=True)
class DecisionSettings:
    """
    Thresholds and weights of the decision engine.
    """

    max_error_chance: float = 0.5
    vqe_max_variables: int = 14
    """Up to this size the structure rule prefers VQE."""

    qaoa_min_variables: int = 16
    """From this size on the structure rule prefers QAOA for QUBOs with a weak field and density."""

    qaoa_always_variables: int = 18
    """From this size on the structure rule prefers QAOA for every QUBO."""

    max_field_coupling_ratio: float = 0.78
    max_density: float = 0.625
    qaoa_max_error_chance: float = 0.4
    history_margin: float = 0.005
    """The history only votes if its best candidate leads the second best by at least this
    mean quality; smaller differences are within the noise of the solution quality."""

    weight_history: float = 0.6
    weight_problem_structure: float = 0.4

    def __post_init__(self) -> None:
        if self.qaoa_min_variables <= self.vqe_max_variables:
            msg = (
                f"qaoa_min_variables ({self.qaoa_min_variables}) must be larger than "
                f"vqe_max_variables ({self.vqe_max_variables})."
            )
            raise ValueError(msg)
        if self.qaoa_always_variables < self.qaoa_min_variables:
            msg = (
                f"qaoa_always_variables ({self.qaoa_always_variables}) must not be smaller "
                f"than qaoa_min_variables ({self.qaoa_min_variables})."
            )
            raise ValueError(msg)


@dataclass(frozen=True)
class Decision:
    """
    Selected candidate with the votes that led to it.
    """

    candidate: Candidate
    fallback_used: bool
    scores: dict[Candidate, float]
    excluded: dict[Candidate, str]
    """Candidates removed by the NISQ Analyzer filter, with the reason."""

    signals: list[SignalResult]
    reasoning: str


def default_candidate(candidates: list[Candidate]) -> Candidate:
    """
    The shallowest VQE, or the shallowest candidate if no VQE is offered.
    """

    preferred = [c for c in candidates if c.algorithm == DEFAULT_ALGORITHM]
    return min(preferred or candidates, key=lambda c: c.layers)


class AlgorithmDecisionEngine:
    """
    Filters the candidates with the NISQ Analyzer results and combines history and the problem
    structure rule into one decision.
    """

    def __init__(self, settings: DecisionSettings):
        self.settings = settings

    def decide(
        self,
        qubo: QUBOProblem,
        candidates: list[CandidateEvaluation],
        similar_records: list[SimilarRecord],
    ) -> Decision:
        """
        Select the candidate for a QUBO.

        :param qubo: The QUBO to solve.
        :param candidates: Circuits and NISQ Analyzer results of all candidates.
        :param similar_records: Records of similar QUBOs, only those with qualities are used.
        """

        excluded = self._nisq_filter(candidates)
        feasible = [c for c in candidates if c.candidate not in excluded]
        signals = [
            self._history_signal(similar_records, feasible),
            self._problem_structure_signal(qubo, feasible),
        ]

        scores = {c.candidate: 0.0 for c in feasible}
        for signal in signals:
            if signal.preferred is not None and signal.preferred in scores:
                scores[signal.preferred] += signal.weight

        reasons = [f"NISQ Analyzer: {_format_exclusions(excluded)}"]
        reasons += [f"{s.name}: {s.explanation}" for s in signals]
        winner = _strict_winner(scores)
        if winner is not None:
            reasons.append(f"Selected {winner} with scores {_format_scores(scores)}.")
            return Decision(
                winner, False, scores, excluded, signals, "\n".join(reasons)
            )

        if feasible:
            fallback = default_candidate([c.candidate for c in feasible])
            reasons.append(
                f"No candidate has a clearly highest score {_format_scores(scores)}, "
                f"selecting the default {fallback}."
            )
        else:
            # Nothing is feasible: prefer a candidate that a QPU can at least execute.
            executable = [c for c in candidates if not _not_executable(c)]
            fallback = default_candidate(
                [c.candidate for c in executable or candidates]
            )
            reasons.append(
                f"No candidate is feasible, selecting the default {fallback}."
            )
        return Decision(fallback, True, scores, excluded, signals, "\n".join(reasons))

    def _nisq_filter(
        self, candidates: list[CandidateEvaluation]
    ) -> dict[Candidate, str]:
        """
        Candidates without a QPU or with a too high error chance, with the reason.

        Without an error chance (NISQ Analyzer unreachable, QPU without error rates) a candidate
        is kept, as nothing speaks against it.
        """

        excluded: dict[Candidate, str] = {}
        for candidate in candidates:
            selection = candidate.qpu_selection
            if _not_executable(candidate):
                excluded[candidate.candidate] = candidate.nisq_error or "no QPU"
            elif (
                selection is not None
                and selection.error_chance is not None
                and selection.error_chance > self.settings.max_error_chance
            ):
                excluded[candidate.candidate] = (
                    f"error chance {selection.error_chance:.3f} on {selection.qpu} exceeds "
                    f"{self.settings.max_error_chance}"
                )
        return excluded

    def _history_signal(
        self, similar_records: list[SimilarRecord], feasible: list[CandidateEvaluation]
    ) -> SignalResult:
        """
        The feasible candidate with the best similarity-weighted mean quality for similar QUBOs.
        """

        name, weight = "History", self.settings.weight_history
        labels = {str(c.candidate): c.candidate for c in feasible}
        totals: dict[Candidate, float] = defaultdict(float)
        weights: dict[Candidate, float] = defaultdict(float)
        for similar in similar_records:
            for label, quality in similar.record.candidate_qualities.items():
                if label in labels:
                    totals[labels[label]] += similar.similarity * quality
                    weights[labels[label]] += similar.similarity

        means = {c: totals[c] / w for c, w in weights.items() if w > 0}
        winner = _strict_winner(means)
        if winner is None:
            explanation = (
                "No quality is known for a feasible candidate on a similar QUBO."
                if not means
                else f"Mean qualities on similar QUBOs are tied {_format_scores(means)}."
            )
            return SignalResult(
                name=name, weight=weight, preferred=None, explanation=explanation
            )

        runner_up = max((m for c, m in means.items() if c != winner), default=-math.inf)
        lead = means[winner] - runner_up
        if lead < self.settings.history_margin:
            return SignalResult(
                name=name,
                weight=weight,
                preferred=None,
                explanation=(
                    f"{winner} leads by only {lead:.3f} (margin "
                    f"{self.settings.history_margin}) in the similarity-weighted means "
                    f"{_format_scores(means)}."
                ),
            )

        count = sum(
            1 for s in similar_records if str(winner) in s.record.candidate_qualities
        )
        return SignalResult(
            name=name,
            weight=weight,
            preferred=winner,
            explanation=(
                f"{winner} has the best mean quality on {count} similar QUBO(s), "
                f"similarity-weighted means {_format_scores(means)}."
            ),
        )

    def _problem_structure_signal(
        self, qubo: QUBOProblem, feasible: list[CandidateEvaluation]
    ) -> SignalResult:
        """
        VQE up to ``vqe_max_variables``, no vote below ``qaoa_min_variables``, QAOA from
        ``qaoa_always_variables`` on. In between QAOA if the field/coupling ratio and the density
        are at most their limits, otherwise VQE.

        A QAOA vote needs a feasible QAOA candidate whose error chance is unknown or at most
        ``qaoa_max_error_chance``; it goes to the deepest such QAOA. Otherwise the rule votes for
        VQE: the feasible VQE with the lowest error chance, or the shallowest one if the NISQ
        Analyzer gave no error chances.
        """

        settings = self.settings
        name, weight = "Problem structure rule", settings.weight_problem_structure
        n = qubo.num_variables
        if settings.vqe_max_variables < n < settings.qaoa_min_variables:
            return SignalResult(
                name=name,
                weight=weight,
                preferred=None,
                explanation=(
                    f"{n} variables lie between {settings.vqe_max_variables} and "
                    f"{settings.qaoa_min_variables}, where neither algorithm is clearly "
                    "better."
                ),
            )

        if n <= settings.vqe_max_variables:
            algorithm = QuantumAlgorithm.VQE
            reason = f"{n} variables (at most {settings.vqe_max_variables})"
        elif n >= settings.qaoa_always_variables:
            algorithm = QuantumAlgorithm.QAOA
            reason = f"{n} variables (at least {settings.qaoa_always_variables})"
        else:
            ratio, density = qubo.field_coupling_ratio, qubo.density
            weak = (
                ratio <= settings.max_field_coupling_ratio
                and density <= settings.max_density
            )
            algorithm = QuantumAlgorithm.QAOA if weak else QuantumAlgorithm.VQE
            reason = (
                f"{n} variables with field/coupling ratio {ratio:.2f} "
                f"(limit {settings.max_field_coupling_ratio}) and density {density:.2f} "
                f"(limit {settings.max_density})"
            )

        if algorithm == QuantumAlgorithm.QAOA:
            qaoa = [c for c in feasible if c.algorithm == QuantumAlgorithm.QAOA]
            limit = settings.qaoa_max_error_chance
            usable = [c for c in qaoa if _error_chance_at_most(c, limit)]
            if usable:
                best = max(usable, key=lambda c: c.layers)
                return SignalResult(
                    name=name,
                    weight=weight,
                    preferred=best.candidate,
                    explanation=(
                        f"{reason} favour QAOA; {best.candidate} is the deepest feasible QAOA "
                        f"with an error chance of at most {limit}."
                    ),
                )
            reason += (
                f" favour QAOA, but no QAOA candidate has an error chance of at most {limit}"
                if qaoa
                else " favour QAOA, but no QAOA candidate is feasible"
            )
        else:
            reason += " favour VQE"

        options = [c for c in feasible if c.algorithm == QuantumAlgorithm.VQE]
        if not options:
            return SignalResult(
                name=name,
                weight=weight,
                preferred=None,
                explanation=f"{reason}, and no VQE candidate is feasible.",
            )

        best = min(options, key=_error_chance_then_depth)
        return SignalResult(
            name=name,
            weight=weight,
            preferred=best.candidate,
            explanation=(
                f"{reason}; voting for {best.candidate}, the VQE with the lowest error chance."
            ),
        )


def _not_executable(candidate: CandidateEvaluation) -> bool:
    """The NISQ Analyzer analyzed the circuit but found no QPU for it."""

    return candidate.nisq_reachable and candidate.qpu_selection is None


def _error_chance_at_most(candidate: CandidateEvaluation, limit: float) -> bool:
    """Whether the error chance is unknown or at most ``limit``."""

    selection = candidate.qpu_selection
    chance = None if selection is None else selection.error_chance
    return chance is None or chance <= limit


def _error_chance_then_depth(candidate: CandidateEvaluation) -> tuple[float, int]:
    selection = candidate.qpu_selection
    chance = None if selection is None else selection.error_chance
    return (math.inf if chance is None else chance, candidate.layers)


def _strict_winner(scores: dict[Candidate, float]) -> Candidate | None:
    """
    Candidate with a positive score higher than all others, if any.
    """

    if not scores:
        return None
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best, best_score = ranked[0]
    if best_score <= 0:
        return None
    if len(ranked) > 1 and (
        ranked[1][1] >= best_score or math.isclose(ranked[1][1], best_score)
    ):
        return None
    return best


def _format_scores(scores: dict[Candidate, float]) -> str:
    return "{" + ", ".join(f"{c}: {s:.2f}" for c, s in scores.items()) + "}"


def _format_exclusions(excluded: dict[Candidate, str]) -> str:
    if not excluded:
        return "all candidates are feasible."
    return (
        "removed "
        + "; ".join(f"{c} ({reason})" for c, reason in excluded.items())
        + "."
    )

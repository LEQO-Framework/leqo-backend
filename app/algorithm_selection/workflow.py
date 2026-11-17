"""
Workflow that selects the quantum algorithm for a QUBO.

QUBO -> circuits of all candidates -> NISQ Analyzer (filter) -> history -> decision
-> execution record.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.algorithm_selection.decision_engine import AlgorithmDecisionEngine
from app.algorithm_selection.models import AlgorithmSelectionResult, QUBOProblem
from app.algorithm_selection.qasm_service import QuboCircuitService
from app.algorithm_selection.repository import (
    ExecutionRecordRepository,
    SimilaritySettings,
)
from app.model.database_model import ExecutionRecord


class AlgorithmSelectionWorkflow:
    """
    Runs the algorithm selection for a QUBO and records the result.
    """

    def __init__(
        self,
        circuit_service: QuboCircuitService,
        repository: ExecutionRecordRepository,
        decision_engine: AlgorithmDecisionEngine,
        similarity_settings: SimilaritySettings,
    ):
        self.circuit_service = circuit_service
        self.repository = repository
        self.decision_engine = decision_engine
        self.similarity_settings = similarity_settings

    async def run(self, qubo: QUBOProblem) -> AlgorithmSelectionResult:
        """
        Select the algorithm for a QUBO and store an :class:`~app.model.database_model.ExecutionRecord`.
        """

        candidates = await self.circuit_service.analyze(qubo)
        similar_records = await self.repository.find_similar(
            qubo, self.similarity_settings, only_with_qualities=True
        )
        decision = self.decision_engine.decide(qubo, candidates, similar_records)
        selected = next(c for c in candidates if c.candidate == decision.candidate)
        selection = selected.qpu_selection

        record = await self.repository.save(
            ExecutionRecord(
                created_at=datetime.now(UTC),
                input_qubo=qubo.model_dump(mode="json"),
                num_variables=qubo.num_variables,
                density=qubo.density,
                variable_names=qubo.variable_names,
                selected_algorithm=decision.candidate.algorithm.value,
                selected_layers=decision.candidate.layers,
                generated_qasm=selected.qasm,
                selected_qpu=None if selection is None else selection.qpu,
                selected_provider=None if selection is None else selection.provider,
                error_chance=None if selection is None else selection.error_chance,
                reasoning=decision.reasoning,
                candidate_evaluations=[
                    c.model_dump(mode="json", exclude={"qasm"}) for c in candidates
                ],
            )
        )

        names = qubo.variable_names
        return AlgorithmSelectionResult(
            record_id=record.id,
            selected_algorithm=decision.candidate.algorithm,
            selected_layers=decision.candidate.layers,
            fallback_used=decision.fallback_used,
            scores={str(c): score for c, score in decision.scores.items()},
            excluded_candidates={
                str(c): reason for c, reason in decision.excluded.items()
            },
            signals=decision.signals,
            reasoning=decision.reasoning,
            generated_qasm=selected.qasm,
            selected_qpu=selection,
            qubit_variables=[names[i] for i in qubo.coupled_variables],
            candidates=candidates,
            similar_record_ids=[s.record.id for s in similar_records],
        )

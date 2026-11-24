"""
Fastapi endpoints of the QUBO algorithm selection workflow.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.params import Depends
from sqlalchemy.ext.asyncio import AsyncEngine

from app.algorithm_selection.decision_engine import (
    AlgorithmDecisionEngine,
    DecisionSettings,
)
from app.algorithm_selection.models import (
    AlgorithmSelectionResult,
    Candidate,
    ExecutionOutcome,
    ExecutionRecordResponse,
    QuantumAlgorithm,
    QUBOProblem,
)
from app.algorithm_selection.nisq_client import NisqAnalyzerClient
from app.algorithm_selection.qasm_service import QuboCircuitService
from app.algorithm_selection.repository import (
    ExecutionRecordRepository,
    SimilaritySettings,
)
from app.algorithm_selection.workflow import AlgorithmSelectionWorkflow
from app.config import Settings
from app.services import get_db_engine, get_settings

router = APIRouter(prefix="/qubo/algorithm-selection", tags=["algorithm-selection"])


def get_execution_record_repository(
    engine: Annotated[AsyncEngine, Depends(get_db_engine)],
) -> ExecutionRecordRepository:
    return ExecutionRecordRepository(engine)


async def get_nisq_analyzer_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncGenerator[NisqAnalyzerClient]:
    async with NisqAnalyzerClient(
        str(settings.nisq_analyzer_url),
        mcda_method=settings.nisq_analyzer_mcda_method,
        allowed_providers=settings.nisq_analyzer_allowed_providers,
        compilers=settings.nisq_analyzer_compilers,
        tokens=settings.nisq_analyzer_tokens,
        poll_interval=settings.nisq_analyzer_poll_interval_seconds,
        timeout=settings.nisq_analyzer_timeout_seconds,
    ) as client:
        yield client


def candidates(settings: Settings) -> list[Candidate]:
    """
    One candidate per configured QAOA and VQE depth.
    """

    return [
        Candidate(algorithm=QuantumAlgorithm.QAOA, layers=p)
        for p in sorted(set(settings.algorithm_selection_qaoa_layers))
    ] + [
        Candidate(algorithm=QuantumAlgorithm.VQE, layers=layers)
        for layers in sorted(set(settings.algorithm_selection_vqe_layers))
    ]


def get_algorithm_selection_workflow(
    settings: Annotated[Settings, Depends(get_settings)],
    nisq_client: Annotated[NisqAnalyzerClient, Depends(get_nisq_analyzer_client)],
    repository: Annotated[
        ExecutionRecordRepository, Depends(get_execution_record_repository)
    ],
) -> AlgorithmSelectionWorkflow:
    return AlgorithmSelectionWorkflow(
        QuboCircuitService(nisq_client, candidates(settings)),
        repository,
        AlgorithmDecisionEngine(
            DecisionSettings(
                max_error_chance=settings.algorithm_selection_max_error_chance,
                vqe_max_variables=settings.algorithm_selection_vqe_max_variables,
                qaoa_min_variables=settings.algorithm_selection_qaoa_min_variables,
                qaoa_always_variables=settings.algorithm_selection_qaoa_always_variables,
                max_field_coupling_ratio=settings.algorithm_selection_max_field_coupling_ratio,
                max_density=settings.algorithm_selection_max_density,
                qaoa_max_error_chance=settings.algorithm_selection_qaoa_max_error_chance,
                history_margin=settings.algorithm_selection_history_margin,
                weight_history=settings.algorithm_selection_weight_history,
                weight_problem_structure=settings.algorithm_selection_weight_problem_structure,
            )
        ),
        SimilaritySettings(
            variable_tolerance=settings.algorithm_selection_history_variable_tolerance,
            density_tolerance=settings.algorithm_selection_history_density_tolerance,
            size_scale=settings.algorithm_selection_history_size_scale,
            density_scale=settings.algorithm_selection_history_density_scale,
            field_scale=settings.algorithm_selection_history_field_scale,
            limit=settings.algorithm_selection_history_limit,
        ),
    )


@router.post("")
async def post_algorithm_selection(
    qubo: QUBOProblem,
    workflow: Annotated[
        AlgorithmSelectionWorkflow, Depends(get_algorithm_selection_workflow)
    ],
) -> AlgorithmSelectionResult:
    """
    Select the quantum algorithm for a QUBO.

    Generates the circuit of every candidate, lets the NISQ Analyzer select and rank QPUs for each
    and removes infeasible candidates, combines the history of similar QUBOs with the problem
    structure rule and stores the decision.
    Waits for the NISQ Analyzer, which can take minutes.
    """

    return await workflow.run(qubo)


@router.get("/history")
async def get_algorithm_selection_history(
    repository: Annotated[
        ExecutionRecordRepository, Depends(get_execution_record_repository)
    ],
    limit: Annotated[int, Query(gt=0, le=500)] = 50,
) -> list[ExecutionRecordResponse]:
    """
    List the most recent algorithm selections.
    """

    records = await repository.list_recent(limit)
    return [ExecutionRecordResponse.model_validate(r) for r in records]


@router.get("/{record_id}")
async def get_algorithm_selection(
    record_id: UUID,
    repository: Annotated[
        ExecutionRecordRepository, Depends(get_execution_record_repository)
    ],
) -> ExecutionRecordResponse:
    """
    Fetch a stored algorithm selection.
    """

    record = await repository.get(record_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"No algorithm selection with id '{record_id}'."
        )
    return ExecutionRecordResponse.model_validate(record)


@router.put("/{record_id}/outcome")
async def put_algorithm_selection_outcome(
    record_id: UUID,
    outcome: ExecutionOutcome,
    repository: Annotated[
        ExecutionRecordRepository, Depends(get_execution_record_repository)
    ],
) -> ExecutionRecordResponse:
    """
    Report whether solving the QUBO with the selected candidate succeeded and how well.

    The quality is stored for the selected candidate; the history prefers the candidates with the
    best qualities for similar QUBOs. Selections without a reported outcome are not used.
    """

    record = await repository.set_outcome(record_id, outcome.succeeded, outcome.quality)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"No algorithm selection with id '{record_id}'."
        )
    return ExecutionRecordResponse.model_validate(record)

"""
Persistence of :class:`~app.model.database_model.ExecutionRecord`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import String, cast, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.algorithm_selection.models import Candidate, QuantumAlgorithm, QUBOProblem
from app.model.database_model import ExecutionRecord


@dataclass(frozen=True)
class SimilarRecord:
    """
    A past record and its similarity in ``[0, 1]`` to a QUBO.
    """

    record: ExecutionRecord
    similarity: float


@dataclass(frozen=True)
class SimilaritySettings:
    """
    Which past records count as similar to a QUBO and how similar they are.

    Records within ``variable_tolerance`` (relative) and ``density_tolerance`` (absolute) are
    considered; of these, the ``limit`` nearest in the feature space of size, density and
    field/coupling ratio are used (k nearest neighbours). The distance adds the relative size
    difference, the density difference and the difference of ``log(1 + field/coupling ratio)``,
    each divided by its scale; a scale of 0 ignores the feature.
    """

    variable_tolerance: float = 0.2
    density_tolerance: float = 1.0
    size_scale: float = 0.2
    density_scale: float = 0.1
    field_scale: float = 0.5
    limit: int = 50


def distance(
    qubo: QUBOProblem,
    num_variables: int,
    density: float,
    field_coupling_ratio: float,
    settings: SimilaritySettings,
) -> float:
    """
    Distance of a QUBO to a record with the given features, see :class:`SimilaritySettings`.
    """

    features = [
        (
            abs(qubo.num_variables - num_variables) / qubo.num_variables,
            settings.size_scale,
        ),
        (abs(qubo.density - density), settings.density_scale),
        (
            abs(
                math.log1p(qubo.field_coupling_ratio) - math.log1p(field_coupling_ratio)
            ),
            settings.field_scale,
        ),
    ]
    return sum(difference / scale for difference, scale in features if scale > 0)


def record_field_coupling_ratio(record: ExecutionRecord) -> float:
    """Field/coupling ratio of the stored QUBO of a record."""

    return QUBOProblem.model_validate(record.input_qubo).field_coupling_ratio


def similarity(
    qubo: QUBOProblem, record: ExecutionRecord, settings: SimilaritySettings
) -> float:
    """
    Similarity ``exp(-distance^2)`` in ``(0, 1]`` of a record to a QUBO.
    """

    return math.exp(
        -(
            distance(
                qubo,
                record.num_variables,
                record.density,
                record_field_coupling_ratio(record),
                settings,
            )
            ** 2
        )
    )


class ExecutionRecordRepository:
    """
    Stores execution records and finds records of similar QUBOs.
    """

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def save(self, record: ExecutionRecord) -> ExecutionRecord:
        async with AsyncSession(self.engine, expire_on_commit=False) as session:
            session.add(record)
            await session.commit()
        return record

    async def get(self, record_id: UUID) -> ExecutionRecord | None:
        async with AsyncSession(self.engine) as session:
            return await session.get(ExecutionRecord, record_id)

    async def list_recent(self, limit: int) -> list[ExecutionRecord]:
        async with AsyncSession(self.engine) as session:
            result = await session.execute(
                select(ExecutionRecord)
                .order_by(ExecutionRecord.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def set_outcome(
        self, record_id: UUID, succeeded: bool, quality: float | None = None
    ) -> ExecutionRecord | None:
        """
        Store whether solving the QUBO with the selected candidate succeeded and how well.

        :param quality: Solution quality in ``[0, 1]`` of the selected candidate;
            without it, a success counts as 1 and a failure as 0.
        """

        async with AsyncSession(self.engine, expire_on_commit=False) as session:
            record = await session.get(ExecutionRecord, record_id)
            if record is None:
                return None
            selected = Candidate(
                algorithm=QuantumAlgorithm(record.selected_algorithm),
                layers=record.selected_layers,
            )
            if quality is None:
                quality = 1.0 if succeeded else 0.0
            record.succeeded = succeeded
            # A new dict, so SQLAlchemy notices the change of the JSON column.
            record.candidate_qualities = {
                **record.candidate_qualities,
                str(selected): quality,
            }
            await session.commit()
            return record

    async def find_similar(
        self,
        qubo: QUBOProblem,
        settings: SimilaritySettings,
        *,
        only_with_qualities: bool = False,
    ) -> list[SimilarRecord]:
        """
        Find the records nearest to a QUBO in size, density and field/coupling ratio.

        :param qubo: The QUBO to compare with.
        :param settings: Tolerances, scales and number of records.
        :param only_with_qualities: Only return records with at least one candidate quality,
            i.e. with a reported outcome.
        :return: At most ``settings.limit`` similar records, most similar first.
        """

        n = qubo.num_variables
        variable_delta = math.floor(n * settings.variable_tolerance)
        tolerance = settings.density_tolerance
        query = select(ExecutionRecord).where(
            ExecutionRecord.num_variables.between(
                n - variable_delta, n + variable_delta
            ),
            ExecutionRecord.density.between(
                qubo.density - tolerance, qubo.density + tolerance
            ),
        )
        if only_with_qualities:
            query = query.where(
                cast(ExecutionRecord.candidate_qualities, String) != "{}"
            )
        query = query.order_by(ExecutionRecord.created_at.desc())

        async with AsyncSession(self.engine) as session:
            records = (await session.execute(query)).scalars().all()

        # Stable sort: among equally similar records, the most recent first.
        similar = [SimilarRecord(r, similarity(qubo, r, settings)) for r in records]
        similar.sort(key=lambda s: s.similarity, reverse=True)
        return similar[: settings.limit]

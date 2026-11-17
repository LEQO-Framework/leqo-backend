import math
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.algorithm_selection.models import QUBOProblem
from app.algorithm_selection.repository import (
    ExecutionRecordRepository,
    SimilaritySettings,
    similarity,
)
from app.model.database_model import ExecutionRecord


@pytest_asyncio.fixture
async def repository(engine: AsyncEngine) -> AsyncGenerator[ExecutionRecordRepository]:
    async with AsyncSession(engine) as session:
        await session.execute(delete(ExecutionRecord))
        await session.commit()
    yield ExecutionRecordRepository(engine)


def chain(n: int, names: list[str] | None = None) -> QUBOProblem:
    return QUBOProblem(
        matrix=[[1 if j == i + 1 else 0 for j in range(n)] for i in range(n)],
        variables=names,
    )


def with_field(qubo: QUBOProblem, diagonal: float) -> QUBOProblem:
    """The QUBO with ``diagonal`` added to every linear term."""

    return QUBOProblem(
        matrix=[
            [v + diagonal if i == j else v for j, v in enumerate(row)]
            for i, row in enumerate(qubo.matrix)
        ]
    )


def record(
    qubo: QUBOProblem,
    algorithm: str = "QAOA",
    succeeded: bool | None = None,
    qualities: dict[str, float] | None = None,
) -> ExecutionRecord:
    return ExecutionRecord(
        created_at=datetime.now(UTC),
        input_qubo=qubo.model_dump(mode="json"),
        num_variables=qubo.num_variables,
        density=qubo.density,
        variable_names=qubo.variable_names,
        selected_algorithm=algorithm,
        selected_layers=1,
        generated_qasm="OPENQASM 2.0;",
        selected_qpu="ibmq_athens",
        selected_provider="ibmq",
        error_chance=0.1,
        reasoning="test",
        candidate_evaluations=[],
        succeeded=succeeded,
        candidate_qualities=qualities or {},
    )


@pytest.mark.asyncio
async def test_save_and_get(repository: ExecutionRecordRepository) -> None:
    qubo = chain(4)
    saved = await repository.save(record(qubo))

    loaded = await repository.get(saved.id)

    assert loaded is not None
    assert loaded.input_qubo == {
        "matrix": qubo.matrix,
        "variables": None,
        "offset": 0.0,
    }
    assert loaded.variable_names == ["x0", "x1", "x2", "x3"]
    assert loaded.succeeded is None
    assert loaded.candidate_qualities == {}


@pytest.mark.asyncio
async def test_set_outcome(repository: ExecutionRecordRepository) -> None:
    saved = await repository.save(record(chain(4)))

    updated = await repository.set_outcome(saved.id, succeeded=True)

    assert updated is not None
    assert updated.succeeded is True
    loaded = await repository.get(saved.id)
    assert loaded is not None
    assert loaded.succeeded is True
    # Without a quality, a success counts as 1 for the selected candidate.
    assert loaded.candidate_qualities == {"QAOA p=1": 1.0}


@pytest.mark.asyncio
async def test_set_outcome_with_quality_keeps_other_qualities(
    repository: ExecutionRecordRepository,
) -> None:
    saved = await repository.save(record(chain(4), qualities={"VQE L=1": 0.9}))

    await repository.set_outcome(saved.id, succeeded=False, quality=0.4)

    loaded = await repository.get(saved.id)
    assert loaded is not None
    assert loaded.candidate_qualities == {"VQE L=1": 0.9, "QAOA p=1": 0.4}


@pytest.mark.asyncio
async def test_find_similar_filters_size_and_density(
    repository: ExecutionRecordRepository,
) -> None:
    near = await repository.save(record(chain(9)))
    exact = await repository.save(record(chain(10)))
    await repository.save(record(chain(20)))
    dense = QUBOProblem(matrix=[[1] * 10 for _ in range(10)])
    await repository.save(record(dense))

    found = await repository.find_similar(
        chain(10), SimilaritySettings(density_tolerance=0.15)
    )

    assert [s.record.id for s in found] == [exact.id, near.id]
    assert found[0].similarity == pytest.approx(1.0)
    assert found[1].similarity < 1.0


@pytest.mark.asyncio
async def test_find_similar_returns_the_nearest_records(
    repository: ExecutionRecordRepository,
) -> None:
    exact = await repository.save(record(chain(10)))
    strong_field = await repository.save(record(with_field(chain(10), 2.0)))
    near = await repository.save(record(chain(9)))

    found = await repository.find_similar(chain(10), SimilaritySettings(limit=2))

    assert [s.record.id for s in found] == [exact.id, near.id]
    assert strong_field.id not in {s.record.id for s in found}


@pytest.mark.asyncio
async def test_find_similar_only_with_qualities(
    repository: ExecutionRecordRepository,
) -> None:
    trained = await repository.save(record(chain(5), qualities={"VQE L=1": 0.9}))
    await repository.save(record(chain(5), "QAOA"))

    found = await repository.find_similar(
        chain(5),
        SimilaritySettings(variable_tolerance=0, density_tolerance=0),
        only_with_qualities=True,
    )

    assert [s.record.id for s in found] == [trained.id]


def test_similarity_decreases_with_the_feature_distance() -> None:
    qubo = chain(10, [f"a{i}" for i in range(10)])
    size_and_density = SimilaritySettings(
        size_scale=0.1, density_scale=0.1, field_scale=0
    )

    # Variable names do not matter, only size, density and field/coupling ratio.
    assert similarity(qubo, record(chain(10)), SimilaritySettings()) == pytest.approx(
        1.0
    )
    size_distance = 1 / 10 / 0.1
    density_distance = abs(qubo.density - chain(9).density) / 0.1
    assert similarity(qubo, record(chain(9)), size_and_density) == pytest.approx(
        math.exp(-((size_distance + density_distance) ** 2))
    )

    field = with_field(chain(10), 2.0)
    field_distance = (
        abs(
            math.log1p(qubo.field_coupling_ratio)
            - math.log1p(field.field_coupling_ratio)
        )
        / 0.5
    )
    assert similarity(
        qubo, record(field), SimilaritySettings(field_scale=0.5)
    ) == pytest.approx(math.exp(-(field_distance**2)))
    # A scale of 0 ignores the feature.
    assert similarity(qubo, record(field), size_and_density) == pytest.approx(1.0)

"""
Utils used throughout the whole application.
"""

from collections.abc import Callable
from typing import TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import selectinload

from app.model.CompileRequest import ImplementationNode
from app.model.database_model import (
    CompileResult,
    EnrichResult,
    SingleEnrichResult,
    StatusResponseDb,
)
from app.model.exceptions import LeqoProblemDetails
from app.model.StatusResponse import (
    CreatedStatus,
    FailedStatus,
    Progress,
    StatusResponse,
    StatusType,
    SuccessStatus,
)

TParam = TypeVar("TParam")
TReturn = TypeVar("TReturn")


def opt_call(func: Callable[[TParam], TReturn], arg: TParam | None) -> TReturn | None:
    """
    Optional chaining for function calls.

    :param func: Function to call if arg is not None
    :param arg: Argument to pass to func
    :return: Result of func or None
    """

    if arg is None:
        return None

    return func(arg)


T = TypeVar("T")


def not_none[T](value: T | None, error_msg: str) -> T:
    """
    Returns value if not none or raises exception.

    :param value: Value to check.
    :param error_msg: Message to throw.
    :return: The none-none value.
    """

    if value is None:
        raise Exception(error_msg)

    return value


def not_none_or[T](value: T | None, default_value: T) -> T:
    """
    Nullish coalescence - `??` operator.
    Returns `value` if not `None`.
    Else, returns `default_value`.
    """

    if value is None:
        return default_value

    return value


def duplicates[T](list: list[T]) -> set[T]:
    """
    Returns set of duplicate items.
    """
    seen = set()
    result = set()
    for item in list:
        if item in seen:
            result.add(item)
        else:
            seen.add(item)
    return result


async def add_status_response_to_db(
    engine: AsyncEngine, status: StatusResponse
) -> None:
    """
    Add the :class:`~app.model.StatusResponse.StatusResponse` to the database

    :param engine: Database to insert the :class:`~app.model.StatusResponse.StatusResponse` in
    :param status: The :class:`~app.model.StatusResponse.StatusResponse` to add to the database
    """
    process_state = StatusResponseDb(
        id=status.uuid,
        status=status.status,
        createdAt=status.createdAt,
        completedAt=status.completedAt,
        progressPercentage=status.progress.percentage if status.progress else None,
        progressCurrentStep=status.progress.currentStep if status.progress else None,
        result=status.result,
    )

    async with AsyncSession(engine) as session:
        session.add(process_state)
        await session.commit()


async def update_status_response_in_db(
    engine: AsyncEngine, new_state: StatusResponse
) -> None:
    """
    Update the :class:`~app.model.StatusResponse.StatusResponse` in the database by replacing the row.
    """
    new_process_state = StatusResponseDb(
        id=new_state.uuid,
        status=new_state.status,
        createdAt=new_state.createdAt,
        completedAt=new_state.completedAt,
        progressPercentage=new_state.progress.percentage,
        progressCurrentStep=new_state.progress.currentStep,
        result=new_state.result.model_dump_json()
        if isinstance(new_state.result, LeqoProblemDetails)
        else new_state.result,
    )
    async with AsyncSession(engine) as session:
        await session.merge(new_process_state)
        await session.commit()


async def get_status_response_from_db(
    engine: AsyncEngine, uuid: UUID
) -> StatusResponse | None:
    """
    Get the instance of :class:`~app.model.StatusResponse.StatusResponse` with the given uuid from the database

    :param engine: Database engine to get the :class:`~app.model.StatusResponse.StatusResponse` from
    :param uuid: UUID of the :class:`~app.model.StatusResponse.StatusResponse` to retrieve
    :return: The :class:`~app.model.StatusResponse.StatusResponse` if found, otherwise None
    """
    async with AsyncSession(engine) as session:
        process_state_db = await session.get(StatusResponseDb, uuid)
        if process_state_db is None:
            return None

        progress = Progress(
            percentage=process_state_db.progressPercentage,
            currentStep=process_state_db.progressCurrentStep,
        )

        match process_state_db.status:
            case StatusType.IN_PROGRESS:
                return CreatedStatus(
                    uuid=uuid, createdAt=process_state_db.createdAt, progress=progress
                )
            case StatusType.COMPLETED:
                return SuccessStatus(
                    uuid=uuid,
                    createdAt=process_state_db.createdAt,
                    completedAt=process_state_db.completedAt,
                    progress=progress,
                    result=process_state_db.result,
                )
            case StatusType.FAILED:
                return FailedStatus(
                    uuid=uuid,
                    createdAt=process_state_db.createdAt,
                    progress=progress,
                    result=LeqoProblemDetails.model_validate_json(
                        process_state_db.result
                    ),
                )


async def add_result_to_db(
    engine: AsyncEngine, uuid: UUID, results: str | list[ImplementationNode]
) -> None:
    """
    Add a result to the database for the given uuid

    :param engine: Database engine to add the result to
    :param uuid: UUID of the process state this result belongs
    :param result: List of :class:`~app.model.CompileRequest.ImplementationNode` to add as results
    """
    processed_result: CompileResult | EnrichResult
    if isinstance(results, str):
        processed_result = CompileResult(id=uuid, implementation=results)
    else:
        processed_result = EnrichResult(id=uuid)
        enrichment_results = [
            SingleEnrichResult(
                impl_id=result.id,
                impl_label=result.label,
                implementation=result.implementation,
                enrich_result=processed_result,
            )
            for result in results
        ]
        processed_result.results = enrichment_results

    async with AsyncSession(engine) as session:
        session.add(processed_result)
        await session.commit()


async def get_results_from_db(
    engine: AsyncEngine, uuid: UUID
) -> str | list[ImplementationNode] | None:
    async with AsyncSession(engine) as session:
        db_result = await session.execute(
            select(CompileResult).where(CompileResult.id == uuid)
        )
        processed_result = db_result.scalar_one_or_none()
        if processed_result:
            return processed_result.implementation

        enrichment_db_result = await session.execute(
            select(EnrichResult)
            .options(selectinload(EnrichResult.results))
            .where(EnrichResult.id == uuid)
        )
        processed_enrichment_result = enrichment_db_result.scalar_one_or_none()
        if processed_enrichment_result:
            return [
                ImplementationNode(
                    id=res.impl_id,
                    label=res.impl_label,
                    type="implementation",
                    implementation=res.implementation,
                )
                for res in processed_enrichment_result.results
            ]
        return None

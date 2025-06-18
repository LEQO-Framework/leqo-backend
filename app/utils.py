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
    ProcessedResults,
    ProcessStates,
    ResultImplementation,
)
from app.model.StatusResponse import Progress, StatusResponse

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


async def addStatusResponseToDB(engine: AsyncEngine, status: StatusResponse) -> None:
    """Add the :class:`StatusResponse` to the database

    :param engine: Database to insert the :class:`StatusResponse` in
    :param status: The :class:`StatusResponse` to add to the database
    """
    process_state = ProcessStates(
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


async def updateStatusResponseInDB(
    engine: AsyncEngine, uuid: UUID, newState: StatusResponse
) -> None:
    """Update the :class:`StatusResponse` in the database

    :param engine: Database engine to update the :class:`StatusResponse` in
    :param uuid: UUID of the :class:`StatusResponse` to update
    :param newState: The new :class:`StatusResponse` to update in the database
    """
    async with AsyncSession(engine) as session:
        state = await session.get(ProcessStates, uuid)
        if state:
            state.id = newState.uuid
            state.status = newState.status
            state.createdAt = newState.createdAt or state.createdAt
            state.completedAt = newState.completedAt or state.completedAt
            if newState.progress:
                state.progressPercentage = newState.progress.percentage
                state.progressCurrentStep = newState.progress.currentStep
            state.result = newState.result or state.result
            await session.commit()


async def getStatusResponseFromDB(
    engine: AsyncEngine, uuid: UUID
) -> StatusResponse | None:
    """Get the instance of :class:`StatusResponse` with the given uuid from the database

    :param engine: Database engine to get the :class:`StatusResponse` from
    :param uuid: UUID of the :class:`StatusResponse` to retrieve
    :return: The :class:`StatusResponse` if found, otherwise None
    """
    async with AsyncSession(engine) as session:
        process_state_db = await session.get(ProcessStates, uuid)
        if process_state_db:
            return StatusResponse(
                uuid=uuid,
                status=process_state_db.status,
                createdAt=process_state_db.createdAt,
                completedAt=process_state_db.completedAt,
                progress=Progress(
                    percentage=process_state_db.progressPercentage,
                    currentStep=process_state_db.progressCurrentStep,
                )
                if process_state_db.progressPercentage is not None
                else None,
                result=process_state_db.result,
            )
        return None


async def addResultToDB(
    engine: AsyncEngine, uuid: UUID, results: list[ImplementationNode]
) -> None:
    """Add a result to the database for the given uuid

    :param engine: Database engine to add the result to
    :param uuid: UUID of the process state this result belongs
    :param result: List of :class:`ImplementationNode` to add as results
    """
    async with AsyncSession(engine) as session:
        processed_result = ProcessedResults(id=uuid)
        result_impls = [
            ResultImplementation(
                impl_id=result.id,
                impl_label=result.label,
                implementation=result.implementation,
                processed_result=processed_result,
            )
            for result in results
        ]
        processed_result.results = result_impls

        session.add(processed_result)
        await session.commit()


async def getResultsFromDB(
    engine: AsyncEngine, uuid: UUID
) -> list[ImplementationNode] | None:
    async with AsyncSession(engine) as session:
        result = await session.execute(
            select(ProcessedResults)
            .options(selectinload(ProcessedResults.results))
            .where(ProcessedResults.id == uuid)
        )
        processed_result = result.scalar_one_or_none()
        if processed_result:
            return [
                ImplementationNode(
                    id=result.impl_id,
                    label=result.impl_label,
                    type="implementation",
                    implementation=result.implementation,
                )
                for result in processed_result.results
            ]
        return None

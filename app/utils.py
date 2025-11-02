"""
Utils used throughout the whole application.
"""

import json
from collections.abc import Callable
from typing import TypeVar
from uuid import UUID

from openqasm3.ast import Program
from openqasm3.printer import dumps
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import selectinload

from app.model.CompileRequest import ImplementationNode
from app.model.database_model import (
    CompileRequestPayload,
    CompileResult,
    EnrichResult,
    QuantumResourceModel,
    ServiceDeploymentModel,
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
        raise RuntimeError(error_msg)

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


def _serialize_payload(payload: object) -> str:
    """
    Serialize payloads before persisting them.
    """

    if isinstance(payload, bytes):
        return payload.decode("utf-8")
    if isinstance(payload, str):
        return payload
    return json.dumps(payload)


def _deserialize_payload(payload: str) -> object:
    """
    Safely deserialize stored payloads back into python types.
    """

    try:
        return json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return payload


def safe_generate_implementation_node(
    node_id: str, impl: Program | str
) -> ImplementationNode:
    """
    Generate an ImplementationNode without raising an error.

    This is used when an error occurred to get the implementation during failure.
    :param node_id: the id used in the frontend
    :param impl: the implementation to use
    """
    if isinstance(impl, Program):
        try:
            impl = dumps(impl)
        except Exception as dump_exc:
            impl = f"Unable to determine implementation because of {dump_exc}"
    return ImplementationNode(id=node_id, implementation=impl)


async def add_status_response_to_db(
    engine: AsyncEngine,
    status: StatusResponse,
    compilation_target: str,
    *,
    name: str | None = None,
    description: str | None = None,
) -> None:
    """
    Add the :class:`~app.model.StatusResponse.StatusResponse` to the database

    :param engine: Database to insert the :class:`~app.model.StatusResponse.StatusResponse` in
    :param status: The :class:`~app.model.StatusResponse.StatusResponse` to add to the database
    :param compilation_target: Compilation target associated with this request
    :param name: Optional name originating from the request metadata
    :param description: Optional description originating from the request metadata
    """
    result_value = (
        status.result.model_dump_json()
        if isinstance(status.result, LeqoProblemDetails)
        else status.result
    )
    process_state = StatusResponseDb(
        id=status.uuid,
        status=status.status,
        createdAt=status.createdAt,
        completedAt=status.completedAt,
        progressPercentage=status.progress.percentage if status.progress else None,
        progressCurrentStep=status.progress.currentStep if status.progress else None,
        result=result_value,
        name=name,
        description=description,
        compilationTarget=compilation_target,
    )

    async with AsyncSession(engine) as session:
        session.add(process_state)
        await session.commit()


async def update_status_response_in_db(
    engine: AsyncEngine,
    new_state: StatusResponse,
    compilation_target: str,
    *,
    name: str | None = None,
    description: str | None = None,
) -> None:
    """
    Update the :class:`~app.model.StatusResponse.StatusResponse` in the database by replacing the row.

    :param engine: Database engine to use.
    :param new_state: New status information to persist.
    :param compilation_target: Compilation target associated with this request.
    :param name: Optional updated name metadata.
    :param description: Optional updated description metadata.
    """
    async with AsyncSession(engine) as session:
        existing_state = await session.get(StatusResponseDb, new_state.uuid)
        stored_name = (
            name if name is not None else getattr(existing_state, "name", None)
        )
        stored_description = (
            description
            if description is not None
            else getattr(existing_state, "description", None)
        )

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
            name=stored_name,
            description=stored_description,
            compilationTarget=compilation_target,
        )

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
    engine: AsyncEngine,
    uuid: UUID,
    results: str | list[ImplementationNode],
    compilation_target: str,
) -> None:
    """
    Add a result to the database for the given uuid

    :param engine: Database engine to add the result to
    :param uuid: UUID of the process state this result belongs
    :param result: List of :class:`~app.model.CompileRequest.ImplementationNode` to add as results
    :param compilation_target: Compilation target associated with this result
    """
    processed_result: CompileResult | EnrichResult
    if isinstance(results, str):
        processed_result = CompileResult(
            id=uuid, implementation=results, compilationTarget=compilation_target
        )
    else:
        processed_result = EnrichResult(id=uuid, compilationTarget=compilation_target)
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


async def get_results_overview_from_db(
    engine: AsyncEngine,
    status: StatusType | None = None,
) -> list[dict[str, object]]:
    """
    Retrieve basic metadata for every stored request.
    """
    async with AsyncSession(engine) as session:
        query = select(
            StatusResponseDb.id,
            StatusResponseDb.createdAt,
            StatusResponseDb.name,
            StatusResponseDb.description,
            StatusResponseDb.status,
        ).order_by(StatusResponseDb.createdAt.desc())

        if status is not None:
            query = query.where(StatusResponseDb.status == status)

        rows = await session.execute(query)

        return [
            {
                "uuid": row.id,
                "created": row.createdAt,
                "name": row.name,
                "description": row.description,
                "status": row.status.value
                if hasattr(row.status, "value")
                else row.status,
            }
            for row in rows.all()
        ]


async def store_compile_request_payload(
    engine: AsyncEngine, uuid: UUID, payload: str
) -> None:
    """
    Persist the original compile request payload.
    """
    async with AsyncSession(engine) as session:
        await session.merge(CompileRequestPayload(id=uuid, payload=payload))
        await session.commit()


async def get_compile_request_payload(engine: AsyncEngine, uuid: UUID) -> str | None:
    """
    Retrieve the original compile request payload if available.
    """
    async with AsyncSession(engine) as session:
        entity = await session.get(CompileRequestPayload, uuid)
        return entity.payload if entity is not None else None


async def store_qrms(engine: AsyncEngine, uuid: UUID, qrms: object | None) -> None:
    """
    Persist the Quantum Resource Models for the given request UUID.
    """

    if qrms is None:
        return

    payload = _serialize_payload(qrms)
    async with AsyncSession(engine) as session:
        await session.merge(QuantumResourceModel(id=uuid, payload=payload))
        await session.commit()


async def get_qrms(engine: AsyncEngine, uuid: UUID) -> object | None:
    """
    Retrieve stored Quantum Resource Models for the given request UUID.
    """

    async with AsyncSession(engine) as session:
        entity = await session.get(QuantumResourceModel, uuid)
        return _deserialize_payload(entity.payload) if entity is not None else None


async def store_service_deployment_models(
    engine: AsyncEngine, uuid: UUID, service_models: object | None
) -> None:
    """
    Persist the Service Deployment Models for the given request UUID.
    """

    if service_models is None:
        return

    payload = _serialize_payload(service_models)
    async with AsyncSession(engine) as session:
        await session.merge(ServiceDeploymentModel(id=uuid, payload=payload))
        await session.commit()


async def get_service_deployment_models(
    engine: AsyncEngine, uuid: UUID
) -> object | None:
    """
    Retrieve stored Service Deployment Models for the given request UUID.
    """

    async with AsyncSession(engine) as session:
        entity = await session.get(ServiceDeploymentModel, uuid)
        return _deserialize_payload(entity.payload) if entity is not None else None

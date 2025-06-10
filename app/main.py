"""
All fastapi endpoints available.
"""

import traceback
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.params import Depends
from starlette.responses import (
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
)

from app.config import Settings
from app.model.CompileRequest import ImplementationNode
from app.model.StatusResponse import Progress, StatusResponse, StatusType
from app.processing import EnrichingProcessorService, MergingProcessorService
from app.services import get_result_url, get_settings, leqo_lifespan

app = FastAPI(lifespan=leqo_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allow_origins,
    allow_credentials=get_settings().cors_allow_credentials,
    allow_methods=get_settings().cors_allow_methods,
    allow_headers=get_settings().cors_allow_headers,
)

# FIXME: these should live in the database
states: dict[UUID, StatusResponse] = {}
results: dict[UUID, str | list[ImplementationNode]] = {}


@app.post("/compile")
def post_compile(
    processor: Annotated[MergingProcessorService, Depends()],
    background_tasks: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_settings)],
) -> RedirectResponse:
    """
    Enqueue a :class:`~fastapi.background.BackgroundTasks` to process the :class:`~app.model.CompileRequest`.
    """

    uuid: UUID = uuid4()
    states[uuid] = StatusResponse.init_status(uuid)

    background_tasks.add_task(process_compile_request, uuid, processor, settings)

    return RedirectResponse(
        url=f"{settings.api_base_url}status/{uuid}",
        status_code=303,
    )


@app.post("/enrich")
async def post_enrich(
    processor: Annotated[EnrichingProcessorService, Depends()],
    background_tasks: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_settings)],
) -> RedirectResponse:
    """
    Enqueue a :class:`~fastapi.background.BackgroundTasks` to enrich all nodes in the :class:`~app.model.CompileRequest`.
    """

    uuid: UUID = uuid4()
    states[uuid] = StatusResponse.init_status(uuid)

    background_tasks.add_task(process_enrich_request, uuid, processor, settings)

    return RedirectResponse(
        url=f"{settings.api_base_url}status/{uuid}",
        status_code=303,
    )


@app.get("/status/{uuid}")
def get_status(uuid: UUID) -> StatusResponse:
    """
    Fetch status of a compile request.

    :raises HTTPException: (Status 404) If no compile request with uuid is found
    """

    if uuid not in states:
        raise HTTPException(
            status_code=404, detail=f"No compile request with uuid '{uuid}' found."
        )

    return states[uuid]


@app.get("/result/{uuid}", response_model=None)
def get_result(uuid: UUID) -> PlainTextResponse | JSONResponse:
    """
    Fetch result of a compile request.

    :raises HTTPException: (Status 404) If no compile request with uuid is found
    """

    if uuid not in results:
        raise HTTPException(
            status_code=404, detail=f"No compile request with uuid '{uuid}' found."
        )

    result = results[uuid]

    if isinstance(result, str):
        return PlainTextResponse(status_code=200, content=result)

    return JSONResponse(status_code=200, content=jsonable_encoder(result))


async def process_compile_request(
    uuid: UUID,
    processor: MergingProcessorService,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """
    Process the :class:`~app.model.CompileRequest`.

    :param uuid: ID of the compile request
    :param processor: Processor for this request
    :param settings: Settings from .env file
    """

    status: StatusType = StatusType.FAILED
    completedAt: datetime | None = None
    result_code: str = ""

    try:
        result_code = await processor.process()
        result_url = get_result_url(uuid, settings)
        status = StatusType.COMPLETED
        completedAt = datetime.now(UTC)
    except Exception as exception:
        result_url = str(exception) or type(exception).__name__

    old_state: StatusResponse = states[uuid]
    states[uuid] = StatusResponse(
        uuid=old_state.uuid,
        status=status,
        createdAt=old_state.createdAt,
        completedAt=completedAt,
        progress=Progress(percentage=100, currentStep="done"),
        result=result_url,
    )

    results[uuid] = result_code


async def process_enrich_request(
    uuid: UUID,
    processor: EnrichingProcessorService,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """
    Enrich all nodes in the :class:`~app.model.CompileRequest`.

    :param uuid: ID of the compile request
    :param processor: Processor for this request
    :param settings: Settings from .env file
    """

    status: StatusType = StatusType.FAILED
    completedAt: datetime | None = None

    try:
        results[uuid] = await processor.enrich_all()

        result_url = get_result_url(uuid, settings)
        status = StatusType.COMPLETED
        completedAt = datetime.now(UTC)
    except Exception as exception:
        result_url = str(exception) or type(exception).__name__

    old_state: StatusResponse = states[uuid]
    states[uuid] = StatusResponse(
        uuid=old_state.uuid,
        status=status,
        createdAt=old_state.createdAt,
        completedAt=completedAt,
        progress=Progress(percentage=100, currentStep="done"),
        result=result_url,
    )


@app.post("/debug/compile", response_class=PlainTextResponse)
async def post_debug_compile(
    processor: Annotated[MergingProcessorService, Depends()],
) -> str:
    """
    Compiles the request to an openqasm3 program in one request.
    No redirects and no polling of different endpoints needed.

    This endpoint should only be used for debugging purposes.
    """

    try:
        return await processor.process()
    except Exception:
        return traceback.format_exc()


@app.post("/debug/enrich")
async def post_debug_enrich(
    processor: Annotated[EnrichingProcessorService, Depends()],
) -> list[ImplementationNode] | str:
    """
    Enriches all nodes in the compile request in one request.
    No redirects and no polling of different endpoints needed.

    This endpoint should only be used for debugging purposes.
    """

    try:
        return await processor.enrich_all()
    except Exception:
        return traceback.format_exc()

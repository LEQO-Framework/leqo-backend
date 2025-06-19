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
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.responses import (
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
)

from app.config import Settings
from app.model.CompileRequest import ImplementationNode
from app.model.StatusResponse import Progress, StatusResponse, StatusType
from app.processing import EnrichingProcessor, MergingProcessor
from app.services import get_db_engine, get_result_url, get_settings, leqo_lifespan
from app.utils import (
    add_result_to_db,
    add_status_response_to_db,
    get_results_from_db,
    get_status_response_from_db,
    update_status_response_in_db,
)

app = FastAPI(lifespan=leqo_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allow_origins,
    allow_credentials=get_settings().cors_allow_credentials,
    allow_methods=get_settings().cors_allow_methods,
    allow_headers=get_settings().cors_allow_headers,
)


@app.post("/compile")
async def post_compile(
    processor: Annotated[
        MergingProcessor, Depends(MergingProcessor.from_compile_request)
    ],
    background_tasks: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_settings)],
    engine: Annotated[AsyncEngine, Depends(get_db_engine)],
) -> RedirectResponse:
    """
    Enqueue a :class:`~fastapi.background.BackgroundTasks` to process the :class:`~app.model.CompileRequest`.
    """

    uuid: UUID = uuid4()
    statusResponse = StatusResponse.init_status(uuid)
    await add_status_response_to_db(engine, statusResponse)

    background_tasks.add_task(
        process_compile_request, uuid, processor, settings, engine
    )

    return RedirectResponse(
        url=f"{settings.api_base_url}status/{uuid}",
        status_code=303,
    )


@app.post("/enrich")
async def post_enrich(
    processor: Annotated[
        EnrichingProcessor, Depends(EnrichingProcessor.from_compile_request)
    ],
    background_tasks: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_settings)],
    engine: Annotated[AsyncEngine, Depends(get_db_engine)],
) -> RedirectResponse:
    """
    Enqueue a :class:`~fastapi.background.BackgroundTasks` to enrich all nodes in the :class:`~app.model.CompileRequest`.
    """

    uuid: UUID = uuid4()
    statusResponse = StatusResponse.init_status(uuid)
    await add_status_response_to_db(engine, statusResponse)

    background_tasks.add_task(process_enrich_request, uuid, processor, settings, engine)

    return RedirectResponse(
        url=f"{settings.api_base_url}status/{uuid}",
        status_code=303,
    )


@app.get("/status/{uuid}")
async def get_status(
    uuid: UUID, engine: Annotated[AsyncEngine, Depends(get_db_engine)]
) -> StatusResponse:
    """
    Fetch status of a compile request.

    :raises HTTPException: (Status 404) If no compile request with uuid is found
    """

    state = await get_status_response_from_db(engine, uuid)

    if state is None:
        raise HTTPException(
            status_code=404, detail=f"No compile request with uuid '{uuid}' found."
        )

    return state


@app.get("/result/{uuid}", response_model=None)
async def get_result(
    uuid: UUID, engine: Annotated[AsyncEngine, Depends(get_db_engine)]
) -> PlainTextResponse | JSONResponse:
    """
    Fetch result of a compile request.

    :raises HTTPException: (Status 404) If no compile request with uuid is found
    """

    result = await get_results_from_db(engine, uuid)

    if result is None:
        raise HTTPException(
            status_code=404, detail=f"No compile request with uuid '{uuid}' found."
        )

    if isinstance(result, str):
        return PlainTextResponse(status_code=200, content=result)

    return JSONResponse(status_code=200, content=jsonable_encoder(result))


async def process_compile_request(
    uuid: UUID, processor: MergingProcessor, settings: Settings, engine: AsyncEngine
) -> None:
    """
    Process the :class:`~app.model.CompileRequest`.

    :param uuid: ID of the compile request
    :param processor: Processor for this request
    :param settings: Settings from .env file
    :param engine: Database engine to use
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

    new_state = StatusResponse(
        uuid=uuid,
        status=status,
        createdAt=None,
        completedAt=completedAt,
        progress=Progress(percentage=100, currentStep="done"),
        result=result_url,
    )
    await update_status_response_in_db(engine, new_state)
    await add_result_to_db(
        engine,
        uuid,
        result_code,
    )


async def process_enrich_request(
    uuid: UUID, processor: EnrichingProcessor, settings: Settings, engine: AsyncEngine
) -> None:
    """
    Enrich all nodes in the :class:`~app.model.CompileRequest`.

    :param uuid: ID of the compile request
    :param processor: Processor for this request
    :param settings: Settings from .env file
    :param engine: Database engine to use
    """

    status: StatusType = StatusType.FAILED
    completedAt: datetime | None = None

    try:
        result_as_impl_node = await processor.enrich_all()
        await add_result_to_db(engine, uuid, result_as_impl_node)

        result_url = get_result_url(uuid, settings)
        status = StatusType.COMPLETED
        completedAt = datetime.now(UTC)
    except Exception as exception:
        result_url = str(exception) or type(exception).__name__
        
    new_state = StatusResponse(
        uuid=uuid,
        status=status,
        createdAt=None,
        completedAt=completedAt,
        progress=Progress(percentage=100, currentStep="done"),
        result=result_url,
    )
    await update_status_response_in_db(engine, new_state)


@app.post("/debug/compile", response_class=PlainTextResponse)
async def post_debug_compile(
    processor: Annotated[
        MergingProcessor, Depends(MergingProcessor.from_compile_request)
    ],
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
    processor: Annotated[
        EnrichingProcessor, Depends(EnrichingProcessor.from_compile_request)
    ],
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

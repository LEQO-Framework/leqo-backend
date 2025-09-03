"""
All fastapi endpoints available.
"""

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
from app.model.exceptions import LeqoProblemDetails
from app.model.StatusResponse import (
    CreatedStatus,
    FailedStatus,
    Progress,
    StatusResponse,
    SuccessStatus,
)
from app.transformation_manager import (
    EnrichingProcessor,
    EnrichmentInserter,
    MergingProcessor,
)
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
    status_response = CreatedStatus.init_status(uuid)
    await add_status_response_to_db(engine, status_response)

    background_tasks.add_task(
        process_compile_request,
        uuid,
        status_response.createdAt,
        processor,
        settings,
        engine,
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
    status_response = CreatedStatus.init_status(uuid)
    await add_status_response_to_db(engine, status_response)

    background_tasks.add_task(
        process_enrich_request,
        uuid,
        status_response.createdAt,
        processor,
        settings,
        engine,
    )

    return RedirectResponse(
        url=f"{settings.api_base_url}status/{uuid}",
        status_code=303,
    )


@app.post(
    "/insert",
    response_model=None,
    response_class=PlainTextResponse,
    responses={
        400: {"model": LeqoProblemDetails},
        500: {"model": LeqoProblemDetails},
    },
)
async def post_insert(
    inserter: Annotated[
        EnrichmentInserter, Depends(EnrichmentInserter.from_insert_request)
    ],
) -> str | JSONResponse:
    """
    Insert enrichments via :class:`~app.model.InsertRequest`.
    """

    try:
        await inserter.insert_all()
        return "success"
    except Exception as ex:
        return LeqoProblemDetails.from_exception(ex).to_response()


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
    uuid: UUID,
    createdAt: datetime,
    processor: MergingProcessor,
    settings: Settings,
    engine: AsyncEngine,
) -> None:
    """
    Process the :class:`~app.model.CompileRequest`.

    :param uuid: ID of the compile request
    :param processor: Processor for this request
    :param settings: Settings from .env file
    :param engine: Database engine to use
    """

    status: SuccessStatus | FailedStatus
    try:
        result = await processor.process()
        await add_result_to_db(engine, uuid, result)

        status = SuccessStatus(
            uuid=uuid,
            createdAt=createdAt,
            completedAt=datetime.now(UTC),
            progress=Progress(percentage=100, currentStep="done"),
            result=get_result_url(uuid, settings),
        )
    except Exception as ex:
        status = FailedStatus(
            uuid=uuid,
            createdAt=createdAt,
            progress=Progress(percentage=100, currentStep="done"),
            result=LeqoProblemDetails.from_exception(ex),
        )

    await update_status_response_in_db(engine, status)


async def process_enrich_request(
    uuid: UUID,
    createdAt: datetime,
    processor: EnrichingProcessor,
    settings: Settings,
    engine: AsyncEngine,
) -> None:
    """
    Enrich all nodes in the :class:`~app.model.CompileRequest`.

    :param uuid: ID of the compile request
    :param processor: Processor for this request
    :param settings: Settings from .env file
    :param engine: Database engine to use
    """

    status: SuccessStatus | FailedStatus
    try:
        result = await processor.enrich_all()
        await add_result_to_db(engine, uuid, result)

        status = SuccessStatus(
            uuid=uuid,
            createdAt=createdAt,
            completedAt=datetime.now(UTC),
            progress=Progress(percentage=100, currentStep="done"),
            result=get_result_url(uuid, settings),
        )
    except Exception as ex:
        status = FailedStatus(
            uuid=uuid,
            createdAt=createdAt,
            progress=Progress(percentage=100, currentStep="done"),
            result=LeqoProblemDetails.from_exception(ex),
        )

    await update_status_response_in_db(engine, status)


@app.post(
    "/debug/compile",
    response_model=None,
    response_class=PlainTextResponse,
    responses={
        400: {"model": LeqoProblemDetails},
        500: {"model": LeqoProblemDetails},
    },
)
async def post_debug_compile(
    processor: Annotated[
        MergingProcessor, Depends(MergingProcessor.from_compile_request)
    ],
) -> str | JSONResponse:
    """
    Compiles the request to an openqasm3 program in one request.
    No redirects and no polling of different endpoints needed.

    This endpoint should only be used for debugging purposes.
    """

    try:
        return await processor.process()
    except Exception as ex:
        return LeqoProblemDetails.from_exception(ex, is_debug=True).to_response()


@app.post(
    "/debug/enrich",
    response_model=list[ImplementationNode],
    responses={
        400: {"model": LeqoProblemDetails},
        500: {"model": LeqoProblemDetails},
    },
)
async def post_debug_enrich(
    processor: Annotated[
        EnrichingProcessor, Depends(EnrichingProcessor.from_compile_request)
    ],
) -> list[ImplementationNode] | JSONResponse:
    """
    Enriches all nodes in the compile request in one request.
    No redirects and no polling of different endpoints needed.

    This endpoint should only be used for debugging purposes.
    """

    try:
        return await processor.enrich_all()
    except Exception as ex:
        return LeqoProblemDetails.from_exception(ex, is_debug=True).to_response()

"""
All fastapi endpoints available.
"""

import traceback
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.params import Depends
from starlette.responses import PlainTextResponse, RedirectResponse

from app.config import Settings
from app.model.CompileRequest import ImplementationNode
from app.model.StatusResponse import Progress, StatusResponse, StatusType
from app.processing import Processor
from app.services import get_result_url, get_settings, leqo_lifespan

app = FastAPI(lifespan=leqo_lifespan)

origins: list[str] = ["*"]  # ToDo: make this configurable

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# FIXME: these should live in the database
states: dict[UUID, StatusResponse] = {}
results: dict[UUID, str] = {}


@app.post("/compile")
def post_compile(
    processor: Annotated[Processor, Depends()],
    background_tasks: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_settings)],
) -> RedirectResponse:
    """
    Queue a compilation request.
    """

    uuid: UUID = uuid4()
    states[uuid] = StatusResponse(
        uuid=uuid,
        status=StatusType.IN_PROGRESS,
        createdAt=datetime.now(UTC),
        completedAt=None,
        progress=Progress(percentage=0, currentStep="init"),
        result=get_result_url(uuid, settings),
    )

    background_tasks.add_task(process_request, uuid, processor, settings)

    return RedirectResponse(
        url=f"{settings.api_base_url}status/{uuid}",
        status_code=303,
    )


@app.get("/status/{uuid}")
def get_status(uuid: UUID) -> StatusResponse:
    """
    Fetch status of a compile request.
    """

    if uuid not in states:
        raise HTTPException(
            status_code=404, detail=f"No compile request with uuid '{uuid}' found."
        )

    return states[uuid]


@app.get("/result/{uuid}", response_class=PlainTextResponse)
def get_result(uuid: UUID) -> str:
    """
    Fetch result of a compile request.

    :raises HTTPException: (Status 404) If no compile request with uuid is found
    """

    if uuid not in results:
        raise HTTPException(
            status_code=404, detail=f"No compile request with uuid '{uuid}' found."
        )

    return results[uuid]


async def process_request(
    uuid: UUID,
    processor: Processor,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """
    Process a compile request in background.

    :param uuid: Id of the compile request
    :param processor: Processor for this request
    """

    status = StatusType.FAILED
    result_code: str = ""

    try:
        result_code = await processor.process()
        result = get_result_url(uuid, settings)
        status = StatusType.COMPLETED
    except Exception as exception:
        result = str(exception) or type(exception).__name__

    old_state: StatusResponse = states[uuid]
    states[uuid] = StatusResponse(
        uuid=old_state.uuid,
        status=status,
        createdAt=old_state.createdAt,
        completedAt=datetime.now(UTC),
        progress=Progress(percentage=100, currentStep="done"),
        result=result,
    )

    results[uuid] = result_code


@app.post("/debug/compile", response_class=PlainTextResponse)
async def debug_compile(processor: Annotated[Processor, Depends()]) -> str:
    """
    Compiles the request to an openqasm3 program in one shot.
    """

    try:
        return await processor.process()
    except Exception:
        return traceback.format_exc()


@app.post("/debug/enrich")
async def debug_enrich(
    processor: Annotated[Processor, Depends()],
) -> list[ImplementationNode] | str:
    """
    Enriches all nodes in the compile request.
    """

    try:
        return [x async for x in processor.enrich()]
    except Exception:
        return traceback.format_exc()

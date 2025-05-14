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

from app.enricher import Enricher
from app.enricher.literals import LiteralEnricherStrategy
from app.enricher.measure import MeasurementEnricherStrategy
from app.enricher.merger import MergerEnricherStrategy
from app.enricher.splitter import SplitterEnricherStrategy
from app.model.CompileRequest import CompileRequest, ImplementationNode
from app.model.StatusBody import Progress, StatusBody, StatusType
from app.processing import Processor

app = FastAPI()

origins: list[str] = ["*"]  # ToDo: make this configurable

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# FIXME: these should live in the database
states: dict[UUID, StatusBody] = {}
results: dict[UUID, str] = {}


def get_enricher() -> Enricher:
    return Enricher(
        LiteralEnricherStrategy(),
        MeasurementEnricherStrategy(),
        SplitterEnricherStrategy(),
        MergerEnricherStrategy(),
    )


@app.post("/compile")
def compile(
    body: CompileRequest,
    background_tasks: BackgroundTasks,
    enricher: Annotated[Enricher, Depends(get_enricher)],
) -> RedirectResponse:
    """
    Queue a compilation request.
    """

    uuid: UUID = uuid4()
    states[uuid] = StatusBody(
        uuid=uuid,
        status=StatusType.IN_PROGRESS,
        createdAt=datetime.now(UTC),
        completedAt=None,
        progress=Progress(percentage=0, currentStep="init"),
        result=f"/result/{uuid}",
    )
    background_tasks.add_task(
        process_request, uuid, body, enricher
    )  # ToDo: Use Celery (?)
    return RedirectResponse(url=f"/status/{uuid}", status_code=303)


@app.get("/status/{uuid}")
def status(uuid: UUID) -> StatusBody:
    """
    Fetch status of a compile request.
    """

    if uuid not in states:
        raise HTTPException(
            status_code=404, detail=f"No compile request with uuid '{uuid}' found."
        )

    return states[uuid]


@app.get("/result/{uuid}", response_class=PlainTextResponse)
def result(uuid: UUID) -> str:
    """
    Fetch result of a compile request.

    :raises HTTPException: (Status 404) If no compile request with uuid is found
    """

    if uuid not in results:
        raise HTTPException(
            status_code=404, detail=f"No compile request with uuid '{uuid}' found."
        )

    return results[uuid]


async def process_request(uuid: UUID, body: CompileRequest, enricher: Enricher) -> None:
    """
    Process a compile request in background.

    :param uuid: Id of the compile request
    :param body: Compile request from frontend
    :param enricher: Enricher used to enrich nodes
    """

    status = StatusType.FAILED
    try:
        result_str = await Processor(body, enricher).process()
        status = StatusType.COMPLETED
    except Exception as exception:
        result_str = str(exception) or type(exception).__name__

    old_state: StatusBody = states[uuid]
    states[uuid] = StatusBody(
        uuid=old_state.uuid,
        status=status,
        createdAt=old_state.createdAt,
        completedAt=datetime.now(UTC),
        progress=Progress(percentage=100, currentStep="done"),
        result=result_str,
    )
    results[uuid] = result_str


@app.post("/debug/compile", response_class=PlainTextResponse)
async def debug_compile(
    body: CompileRequest, enricher: Annotated[Enricher, Depends(get_enricher)]
) -> str:
    """
    Compiles the request to an openqasm3 program in one shot.
    """

    processor = Processor(body, enricher)

    try:
        return await processor.process()
    except Exception:
        return traceback.format_exc()


@app.post("/debug/enrich")
async def debug_enrich(
    body: CompileRequest, enricher: Annotated[Enricher, Depends(get_enricher)]
) -> list[ImplementationNode] | str:
    """
    Enriches all nodes in the compile request.
    """

    processor = Processor(body, enricher)
    try:
        return [x async for x in processor.enrich()]
    except Exception:
        return traceback.format_exc()

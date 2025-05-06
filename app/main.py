"""
All fastapi endpoints available.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse

from app.model.CompileRequest import CompileRequest
from app.model.StatusBody import Progress, StatusBody, StatusType
from app.processing import process

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


@app.post("/compile")
def compile(
    body: CompileRequest, background_tasks: BackgroundTasks
) -> RedirectResponse:
    """
    Queue a compilation request.

    :param body: Compilation request from frontend
    :param background_tasks: Background tasks injected from fastapi
    :return: RedirectResponse to status endpoint
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
    background_tasks.add_task(process_request, body, uuid)  # ToDo: Use Celery (?)
    return RedirectResponse(url=f"/status/{uuid}", status_code=303)


@app.get("/status/{uuid}")
def status(uuid: UUID) -> StatusBody:
    """
    Fetch status of a compile request.

    :param uuid: Id of the compile request
    :return: Current status of the compile request
    """

    if uuid not in states:
        raise HTTPException(
            status_code=404, detail=f"No compile request with uuid '{uuid}' found."
        )

    return states[uuid]


@app.get("/result/{uuid}")
def result(uuid: UUID) -> str:
    """
    Fetch result of a compile request.

    :param uuid: Id of the compile request
    :return: Result of the compile request

    :raises HTTPException: (Status 404) If no compile request with uuid is found
    """

    if uuid not in results:
        raise HTTPException(
            status_code=404, detail=f"No compile request with uuid '{uuid}' found."
        )

    return results[uuid]


async def process_request(body: CompileRequest, uuid: UUID) -> None:
    """
    Process a compile request in background.

    :param body: Compile request from frontend
    :param uuid: Id of the compile request
    """

    status = StatusType.FAILED
    try:
        result_str = await process(body)
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

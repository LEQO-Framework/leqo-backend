"""
All fastapi endpoints available.
"""

import asyncio
import json
import sys
from datetime import UTC, datetime
from typing import Annotated, Literal, cast
from uuid import UUID, uuid4

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.params import Depends
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse, Response

from app.config import Settings
from app.model.CompileRequest import ImplementationNode
from app.model.exceptions import LeqoProblemDetails
from app.model.StatusResponse import (
    CreatedStatus,
    FailedStatus,
    Progress,
    StatusResponse,
    StatusType,
    SuccessStatus,
)
from app.services import (
    get_db_engine,
    get_qrms_url,
    get_request_url,
    get_result_url,
    get_service_deployment_models_url,
    get_settings,
    leqo_lifespan,
)
from app.transformation_manager import (
    EnrichingProcessor,
    EnrichmentInserter,
    MergingProcessor,
    WorkflowProcessor,
)
from app.utils import (
    add_result_to_db,
    add_status_response_to_db,
    get_compile_request_payload,
    get_qrms,
    list_qrm_ids,
    get_service_deployment_models,
    list_service_deployment_ids,
    get_results_from_db,
    get_results_overview_from_db,
    get_status_response_from_db,
    StoredFilePayload,
    store_compile_request_payload,
    store_qrms,
    store_service_deployment_models,
    update_status_response_in_db,
)

"""
Ensure we use the old `WindowsSelectorEventLoopPolicy` on windows
as the postgresql driver cannot work with the modern `ProactorEventLoop`.
"""
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

app = FastAPI(lifespan=leqo_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allow_origins,
    allow_credentials=get_settings().cors_allow_credentials,
    allow_methods=get_settings().cors_allow_methods,
    allow_headers=get_settings().cors_allow_headers,
)


def _get_processor_target(processor: object) -> Literal["qasm", "workflow"]:
    """
    Safely resolve the target representation advertised by a processor.
    """

    value = getattr(processor, "target", "qasm")
    if isinstance(value, str) and value in {"qasm", "workflow"}:
        return cast(Literal["qasm", "workflow"], value)
    return "qasm"


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
    target = _get_processor_target(processor)
    status_response = CreatedStatus.init_status(uuid)
    metadata = getattr(processor, "optimize", None)
    request_name = getattr(metadata, "name", None) if metadata is not None else None
    request_description = (
        getattr(metadata, "description", None) if metadata is not None else None
    )
    original_request = getattr(processor, "original_request", None)
    if original_request is not None:
        await store_compile_request_payload(
            engine, uuid, original_request.model_dump_json()
        )
    await add_status_response_to_db(
        engine,
        status_response,
        target,
        name=request_name,
        description=request_description,
    )

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
    target = _get_processor_target(processor)
    status_response = CreatedStatus.init_status(uuid)
    metadata = getattr(processor, "optimize", None)
    request_name = getattr(metadata, "name", None) if metadata is not None else None
    request_description = (
        getattr(metadata, "description", None) if metadata is not None else None
    )
    original_request = getattr(processor, "original_request", None)
    if original_request is not None:
        await store_compile_request_payload(
            engine, uuid, original_request.model_dump_json()
        )
    await add_status_response_to_db(
        engine,
        status_response,
        target,
        name=request_name,
        description=request_description,
    )

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


async def _resolve_result_response(
    engine: AsyncEngine, uuid: UUID, settings: Settings | None = None
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

    if settings is None:
        settings = get_settings()

    request_link = get_request_url(uuid, settings)
    result_link = get_result_url(uuid, settings)
    qrms_link = get_qrms_url(uuid, settings)
    service_models_link = get_service_deployment_models_url(uuid, settings)
    headers = {
        "Link": ", ".join(
            (
                f'<{request_link}>; rel="request"',
                f'<{result_link}>; rel="result"',
                f'<{qrms_link}>; rel="qrms"',
                f'<{service_models_link}>; rel="service-deployment-models"',
            )
        )
    }

    if isinstance(result, str):
        return PlainTextResponse(status_code=200, content=result, headers=headers)

    return JSONResponse(
        status_code=200, content=jsonable_encoder(result), headers=headers
    )


@app.get("/results", response_model=None)
async def get_result(
    engine: Annotated[AsyncEngine, Depends(get_db_engine)],
    uuid: UUID | None = None,
    status: StatusType | None = None,
) -> PlainTextResponse | JSONResponse:
    """
    Fetch all results metadata or a specific result if a UUID is provided.
    """

    settings = get_settings()

    if uuid is None:
        overview = await get_results_overview_from_db(engine, status=status)
        overview_with_links: list[dict[str, object]] = []
        for item in overview:
            item_uuid = item.get("uuid")
            if not isinstance(item_uuid, UUID):
                msg = "Result overview entry is missing a valid UUID."
                raise RuntimeError(msg)
            overview_with_links.append(
                {
                    **item,
                    "links": {
                        "result": get_result_url(item_uuid, settings),
                        "request": get_request_url(item_uuid, settings),
                        "qrms": get_qrms_url(item_uuid, settings),
                        "serviceDeploymentModels": get_service_deployment_models_url(
                            item_uuid, settings
                        ),
                    },
                }
            )
        return JSONResponse(
            status_code=200, content=jsonable_encoder(overview_with_links)
        )

    return await _resolve_result_response(engine, uuid, settings)


@app.get("/results/{uuid}", response_model=None)
async def get_result_by_path(
    uuid: UUID, engine: Annotated[AsyncEngine, Depends(get_db_engine)]
) -> PlainTextResponse | JSONResponse:
    """
    Fetch result of a compile request by UUID path parameter.
    """

    return await _resolve_result_response(engine, uuid)


@app.get("/request/{uuid}", response_model=None)
async def get_request_payload(
    uuid: UUID, engine: Annotated[AsyncEngine, Depends(get_db_engine)]
) -> JSONResponse:
    """
    Fetch the original compile request payload associated with a UUID.
    """

    payload = await get_compile_request_payload(engine, uuid)
    if payload is None:
        raise HTTPException(
            status_code=404, detail=f"No compile request with uuid '{uuid}' found."
        )

    return JSONResponse(status_code=200, content=json.loads(payload))


@app.get("/qrms", response_model=list[UUID])
async def list_qrms(
    engine: Annotated[AsyncEngine, Depends(get_db_engine)]
) -> list[UUID]:
    """
    Return all UUIDs that currently have stored Quantum Resource Models.
    """

    return await list_qrm_ids(engine)


@app.get("/qrms/{uuid}", response_model=None)
async def get_qrms_payload(
    uuid: UUID, engine: Annotated[AsyncEngine, Depends(get_db_engine)]
) -> Response:
    """
    Fetch the Quantum Resource Models file associated with a UUID.
    """

    stored_file = await get_qrms(engine, uuid)
    if stored_file is None:
        raise HTTPException(
            status_code=404, detail=f"No QRMs with uuid '{uuid}' found."
        )

    headers = {}
    if stored_file.filename:
        safe_filename = stored_file.filename.replace('"', "")
        headers["Content-Disposition"] = f'attachment; filename="{safe_filename}"'

    media_type = stored_file.content_type or "application/octet-stream"
    return Response(content=stored_file.content, media_type=media_type, headers=headers)


@app.get("/service-deployment-models", response_model=list[UUID])
async def list_service_deployment_models(
    engine: Annotated[AsyncEngine, Depends(get_db_engine)]
) -> list[UUID]:
    """
    Return all UUIDs that currently have stored service deployment models.
    """

    return await list_service_deployment_ids(engine)


@app.get("/service-deployment-models/{uuid}", response_model=None)
async def get_service_deployment_models_payload(
    uuid: UUID, engine: Annotated[AsyncEngine, Depends(get_db_engine)]
) -> Response:
    """
    Fetch the Service Deployment Models file associated with a UUID.
    """

    stored_file = await get_service_deployment_models(engine, uuid)
    if stored_file is None:
        raise HTTPException(
            status_code=404,
            detail=f"No service deployment models with uuid '{uuid}' found.",
        )

    headers = {}
    if stored_file.filename:
        safe_filename = stored_file.filename.replace('"', "")
        headers["Content-Disposition"] = f'attachment; filename="{safe_filename}"'

    media_type = stored_file.content_type or "application/octet-stream"
    return Response(content=stored_file.content, media_type=media_type, headers=headers)


@app.post("/qrms/{uuid}", response_model=None, status_code=204)
async def put_qrms_payload(
    uuid: UUID,
    engine: Annotated[AsyncEngine, Depends(get_db_engine)],
    file: UploadFile = File(...),
) -> Response:
    """
    Store or update the Quantum Resource Models file for the given UUID.
    """

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded QRMs file is empty.")

    stored_file = StoredFilePayload(
        content=data,
        filename=file.filename,
        content_type=file.content_type,
    )
    await store_qrms(engine, uuid, stored_file)
    return Response(status_code=204)


@app.post("/service-deployment-models/{uuid}", response_model=None, status_code=204)
async def put_service_deployment_models_payload(
    uuid: UUID,
    engine: Annotated[AsyncEngine, Depends(get_db_engine)],
    file: UploadFile = File(...),
) -> Response:
    """
    Store or update the Service Deployment Models file for the given UUID.
    """

    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=400, detail="Uploaded service deployment models file is empty."
        )

    stored_file = StoredFilePayload(
        content=data,
        filename=file.filename,
        content_type=file.content_type,
    )
    await store_service_deployment_models(engine, uuid, stored_file)
    return Response(status_code=204)


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

    target = _get_processor_target(processor)
    status: SuccessStatus | FailedStatus
    try:
        result: str | list[ImplementationNode]
        if target == "workflow":
            qasm = await processor.process()
            print("QASM")
            print(qasm)
            print("Requets")
            print(processor.original_request)
            workflow_processor = WorkflowProcessor(
                processor.enricher,
                processor.frontend_graph,
                processor.optimize,
                result=qasm,
                original_request=processor.original_request
            )
            workflow_processor.target = target
            result = await workflow_processor.process()
            
            bpmn_xml, qrms = await workflow_processor.process()
            print(f"[INFO] BPMN XML generated ({len(bpmn_xml)} chars)")
            print(f"[INFO] {len(qrms)} QRM ZIPs generated")

            print("[INFO] BPMN XML persisted")
            print(qrms)

            for node_id, zip_bytes in qrms.items():
                qrms_payload = StoredFilePayload(
                    content=zip_bytes,
                    filename=f"Activity_{node_id}.zip",
                    content_type="application/zip",
                )
                await store_qrms(engine, uuid, qrms_payload)
                print(f"[INFO] Stored QRM for node {node_id} in DB")

        else:
            result = await processor.process()
            print(result)
        await add_result_to_db(engine, uuid, bpmn_xml, target)

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

    await update_status_response_in_db(engine, status, target)


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

    target = _get_processor_target(processor)
    status: SuccessStatus | FailedStatus
    try:
        result = await processor.enrich_all()
        await add_result_to_db(engine, uuid, result, target)

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

    await update_status_response_in_db(engine, status, target)


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
        target = _get_processor_target(processor)
        if target == "workflow":
            qasm = await processor.process()
            workflow_processor = WorkflowProcessor(
                processor.enricher,
                processor.frontend_graph,
                processor.optimize,
                result=qasm,
                original_request=processor.original_request
            )
            workflow_processor.target = target
            result = await workflow_processor.process()
            return JSONResponse(status_code=200, content=jsonable_encoder(result))

        return await processor.process()
    except Exception as ex:
        return LeqoProblemDetails.from_exception(ex, is_debug=True).to_response()


@app.post(
    "/debug/workflow",
    response_model=None,
    responses={
        400: {"model": LeqoProblemDetails},
        500: {"model": LeqoProblemDetails},
    },
)
async def post_debug_workflow(
    processor: Annotated[
        MergingProcessor, Depends(MergingProcessor.from_compile_request)
    ],
    settings: Annotated[Settings, Depends(get_settings)],
    engine: Annotated[AsyncEngine, Depends(get_db_engine)],
) -> JSONResponse:
    """
    Process a compile request directly into a workflow representation,
    optionally including QRMs and service deployment models supplied by the client.

    This endpoint should only be used for debugging purposes.
    """

    try:
        processor.target = "workflow"
        workflow_processor = WorkflowProcessor(
            processor.enricher,
            processor.frontend_graph,
            processor.optimize,
        )
        workflow_processor.target = "workflow"
        result = await workflow_processor.process()
        request_uuid = uuid4()

        created_status = CreatedStatus.init_status(request_uuid)
        metadata = getattr(processor.original_request, "metadata", None)
        name = getattr(metadata, "name", None) if metadata is not None else None
        description = (
            getattr(metadata, "description", None) if metadata is not None else None
        )
        original_request = getattr(processor, "original_request", None)

        await add_status_response_to_db(
            engine,
            created_status,
            "workflow",
            name=name,
            description=description,
        )

        if original_request is not None:
            await store_compile_request_payload(
                engine, request_uuid, original_request.model_dump_json()
            )

        await add_result_to_db(engine, request_uuid, result, "workflow")

        success_status = SuccessStatus(
            uuid=request_uuid,
            createdAt=created_status.createdAt,
            completedAt=datetime.now(UTC),
            progress=Progress(percentage=100, currentStep="done"),
            result=get_result_url(request_uuid, settings),
        )

        await update_status_response_in_db(
            engine,
            success_status,
            "workflow",
            name=name,
            description=description,
        )

        response_payload = {
            "uuid": request_uuid,
            "workflow": result,
            "links": {
                "status": f"{settings.api_base_url}status/{request_uuid}",
                "result": get_result_url(request_uuid, settings),
                "request": get_request_url(request_uuid, settings),
                "qrms": get_qrms_url(request_uuid, settings),
                "serviceDeploymentModels": get_service_deployment_models_url(
                    request_uuid, settings
                ),
            },
        }
        return JSONResponse(
            status_code=200, content=jsonable_encoder(response_payload)
        )
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

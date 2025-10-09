import json
import os
from collections.abc import Iterator
from json import JSONDecodeError, dumps
from pathlib import Path
from time import sleep
from typing import TypeVar

import pytest
import yaml
from httpx import Response
from pydantic import BaseModel
from starlette.testclient import TestClient

from app.main import app

TModel = TypeVar("TModel", bound=BaseModel)

SUCCESS_CODE = 200
POLL_INTERVAL = 0.1
MAX_ATTEMPTS = 5
TEST_DIR = Path(__file__).parent


class Baseline(BaseModel):
    request: str
    expected_status: int
    expected_result: str


class InsertBaseline(BaseModel):
    insert_request: str
    insert_status: int
    merge_request: str
    merge_status: int
    merge_result: str


def find_files(model: type[TModel], *paths: Path) -> Iterator[tuple[str, TModel]]:
    for path in paths:
        for _, _, files in os.walk(path):
            for file_name in files:
                file = path / file_name
                with file.open() as f:
                    yield (
                        str(file.relative_to(Path.cwd())),
                        model.model_validate(yaml.safe_load(f)),
                    )


def prettify_json(s: str) -> str:
    return json.dumps(json.loads(s), indent=2)


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


def handle_endpoints(client: TestClient, request: str, first_endpoint: str) -> Response:
    response = client.post(
        first_endpoint,
        headers={"Content-Type": "application/json"},
        content=request,
    )

    data = response.json()
    assert "uuid" in data, f"No uuid in first response: {data}"
    uuid = data["uuid"]
    done = False
    for _ in range(MAX_ATTEMPTS):
        response = client.get(f"/status/{uuid}")
        status = response.json()["status"]
        if status == "completed":
            done = True
            break
        if status == "failed":
            return response
        sleep(POLL_INTERVAL)
    assert done, (
        f"Timeout while waiting {MAX_ATTEMPTS * POLL_INTERVAL}s for the request"
    )

    return client.get(f"/result/{uuid}")


def json_assert(expected: str, actual: str) -> None:
    try:
        pretty_expected = prettify_json(expected)
        pretty_actual = prettify_json(actual)
        print(pretty_actual)
        assert pretty_expected == pretty_actual
    except JSONDecodeError as exc:
        print(exc)
        print(actual)
        assert expected == actual


@pytest.mark.parametrize(
    "test",
    find_files(Baseline, TEST_DIR / "compile"),
    ids=lambda test: test[0],
)
def test_compile(test: tuple[str, Baseline], client: TestClient) -> None:
    _file, base = test
    response = handle_endpoints(client, base.request, "/compile")

    assert base.expected_result == response.text
    assert base.expected_status == response.status_code


@pytest.mark.parametrize(
    "test",
    find_files(Baseline, TEST_DIR / "compile_errors", TEST_DIR / "enrich_errors"),
    ids=lambda test: test[0],
)
def test_compile_errors(test: tuple[str, Baseline], client: TestClient) -> None:
    _file, base = test
    response = handle_endpoints(client, base.request, "/compile")

    result = response.json()["result"]
    json_assert(base.expected_result, dumps(result))
    assert base.expected_status == result["status"]


@pytest.mark.parametrize(
    "test",
    find_files(Baseline, TEST_DIR / "enrich"),
    ids=lambda test: test[0],
)
def test_enrich(test: tuple[str, Baseline], client: TestClient) -> None:
    _file, base = test
    response = handle_endpoints(client, base.request, "/enrich")

    json_assert(base.expected_result, response.text)
    assert base.expected_status == response.status_code


@pytest.mark.parametrize(
    "test",
    find_files(Baseline, TEST_DIR / "enrich_errors"),
    ids=lambda test: test[0],
)
def test_enrich_errors(test: tuple[str, Baseline], client: TestClient) -> None:
    _file, base = test
    response = handle_endpoints(client, base.request, "/enrich")

    result = response.json()["result"]
    json_assert(base.expected_result, dumps(result))
    assert base.expected_status == result["status"]


@pytest.mark.parametrize(
    "test",
    find_files(Baseline, TEST_DIR / "compile"),
    ids=lambda test: test[0],
)
def test_debug_compile(test: tuple[str, Baseline], client: TestClient) -> None:
    _file, base = test
    response = client.post(
        "/debug/compile",
        headers={"Content-Type": "application/json"},
        content=base.request,
    )

    print(response.text)
    assert base.expected_result == response.text
    assert base.expected_status == response.status_code


@pytest.mark.parametrize(
    "test",
    find_files(Baseline, TEST_DIR / "compile_errors", TEST_DIR / "enrich_errors"),
    ids=lambda test: test[0],
)
def test_debug_compile_errors(test: tuple[str, Baseline], client: TestClient) -> None:
    _file, base = test
    response = client.post(
        "/debug/compile",
        headers={"Content-Type": "application/json"},
        content=base.request,
    )

    json_assert(base.expected_result, response.text)
    assert base.expected_status == response.status_code


@pytest.mark.parametrize(
    "test",
    find_files(Baseline, TEST_DIR / "enrich"),
    ids=lambda test: test[0],
)
def test_debug_enrich(test: tuple[str, Baseline], client: TestClient) -> None:
    _file, base = test
    response = client.post(
        "/debug/enrich",
        headers={"Content-Type": "application/json"},
        content=base.request,
    )

    json_assert(base.expected_result, response.text)
    assert base.expected_status == response.status_code


@pytest.mark.parametrize(
    "test",
    find_files(Baseline, TEST_DIR / "enrich_errors"),
    ids=lambda test: test[0],
)
def test_debug_enrich_errors(test: tuple[str, Baseline], client: TestClient) -> None:
    _file, base = test
    response = client.post(
        "/debug/enrich",
        headers={"Content-Type": "application/json"},
        content=base.request,
    )

    json_assert(base.expected_result, response.text)
    assert base.expected_status == response.status_code


@pytest.mark.parametrize(
    "test",
    find_files(InsertBaseline, TEST_DIR / "insert"),
    ids=lambda test: test[0],
)
def test_insert(test: tuple[str, InsertBaseline], client: TestClient) -> None:
    _file, base = test
    response = client.post(
        "/insert",
        headers={"Content-Type": "application/json"},
        content=base.insert_request,
    )
    assert base.insert_status == response.status_code, (
        f"Insert failed with {response.text}"
    )

    response = client.post(
        "/debug/compile",
        headers={"Content-Type": "application/json"},
        content=base.merge_request,
    )
    print(response.text)
    assert base.merge_result == response.text
    assert base.merge_status == response.status_code


def test_result_endpoint_overview(client: TestClient) -> None:
    compile_request = """{
        "metadata": {
            "version": "1.0.0",
            "name": "My Model",
            "description": "This is a model.",
            "author": ""
        },
        "nodes": [
            { "id": "newNode0", "type": "qubit" },
            { "id": "newNode1", "type": "qubit" },
            { "id": "newNode2", "type": "qubit" },
            { "id": "newNode3", "type": "merger", "numberInputs": "3" },
            {
                "id": "newNode5",
                "type": "implementation",
                "implementation": "OPENQASM 3.1;\\n@leqo.input 0\\nqubit[5] q;"
            }
        ],
        "edges": [
            {
                "source": ["newNode3", 0],
                "target": ["newNode5", 0],
                "identifier": null,
                "size": 1
            },
            { "source": ["newNode2", 0], "target": ["newNode3", 2] },
            { "source": ["newNode1", 0], "target": ["newNode3", 1] },
            { "source": ["newNode0", 0], "target": ["newNode3", 0] }
        ]
    }"""

    response = client.post(
        "/compile",
        headers={"Content-Type": "application/json"},
        content=compile_request,
    )

    data = response.json()
    assert "uuid" in data
    uuid = data["uuid"]

    for _ in range(MAX_ATTEMPTS):
        status_response = client.get(f"/status/{uuid}")
        status_payload = status_response.json()
        if status_payload["status"] == "completed":
            break
        if status_payload["status"] == "failed":
            pytest.fail(f"Compilation failed: {status_payload['result']}")
        sleep(POLL_INTERVAL)
    else:
        pytest.fail("Timeout while waiting for compilation request to finish")

    result_response = client.get(f"/result/{uuid}")
    assert result_response.status_code == SUCCESS_CODE

    overview_response = client.get("/result")
    assert overview_response.status_code == SUCCESS_CODE
    overview = overview_response.json()
    assert isinstance(overview, list)

    matches = [entry for entry in overview if entry["uuid"] == uuid]
    assert matches, "Result overview did not contain the created request"
    summary = matches[0]
    assert summary["name"] == "My Model"
    assert summary["description"] == "This is a model."
    assert summary["status"] == "completed"
    assert summary["created"] is not None

    by_uuid_response = client.get(f"/result?uuid={uuid}")
    assert by_uuid_response.status_code == SUCCESS_CODE
    assert by_uuid_response.text == result_response.text

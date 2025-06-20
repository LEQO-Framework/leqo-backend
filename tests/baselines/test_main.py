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

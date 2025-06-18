import json
import os
from collections.abc import Iterator
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


def find_files(path: Path, model: type[TModel]) -> Iterator[tuple[str, TModel]]:
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
        if json.loads(response.text)["status"] == "completed":
            done = True
            break
        sleep(POLL_INTERVAL)
    assert done, (
        f"Timeout while waiting {MAX_ATTEMPTS * POLL_INTERVAL}s for the request"
    )

    return client.get(f"/result/{uuid}")


def json_assert(expected: str, response: Response) -> None:
    if response.status_code == SUCCESS_CODE:
        pretty_text = prettify_json(response.text)
        print(pretty_text)
        assert prettify_json(expected) == pretty_text
    else:
        assert expected == response.text


@pytest.mark.parametrize(
    "test",
    find_files(TEST_DIR / "compile", Baseline),
    ids=lambda test: test[0],
)
def test_compile(test: tuple[str, Baseline], client: TestClient) -> None:
    _file, base = test
    response = handle_endpoints(client, base.request, "/compile")

    assert response.text == base.expected_result
    assert response.status_code == base.expected_status


@pytest.mark.parametrize(
    "test",
    find_files(TEST_DIR / "enrich", Baseline),
    ids=lambda test: test[0],
)
def test_enrich(test: tuple[str, Baseline], client: TestClient) -> None:
    _file, base = test
    response = handle_endpoints(client, base.request, "/enrich")

    json_assert(base.expected_result, response)
    assert response.status_code == base.expected_status


@pytest.mark.parametrize(
    "test",
    find_files(TEST_DIR / "compile", Baseline),
    ids=lambda test: test[0],
)
def test_debug_compile(test: tuple[str, Baseline], client: TestClient) -> None:
    _file, base = test
    response = client.post(
        "/debug/compile",
        headers={"Content-Type": "application/json"},
        content=base.request,
    )

    assert response.text == base.expected_result
    assert response.status_code == base.expected_status


@pytest.mark.parametrize(
    "test",
    find_files(TEST_DIR / "enrich", Baseline),
    ids=lambda test: test[0],
)
def test_debug_enrich(test: tuple[str, Baseline], client: TestClient) -> None:
    _file, base = test
    response = client.post(
        "/debug/enrich",
        headers={"Content-Type": "application/json"},
        content=base.request,
    )

    json_assert(base.expected_result, response)
    assert response.status_code == base.expected_status

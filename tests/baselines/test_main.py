import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import BaseModel
from starlette.testclient import TestClient

from app.main import app
from tests.baselines import find_files

SUCCESS_CODE = 200


def prettify_json(s: str) -> str:
    return json.dumps(json.loads(s), indent=2)


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


class DebugBaseline(BaseModel):
    request: str
    expected_status: int
    expected_result: str


TEST_DIR = Path(__file__).parent


@pytest.mark.parametrize(
    "test",
    find_files(TEST_DIR / "debug" / "compile", DebugBaseline),
)
def test_debug_compile(test: DebugBaseline, client: TestClient) -> None:
    response = client.post(
        "/debug/compile",
        headers={"Content-Type": "application/json"},
        content=test.request,
    )

    print(response.text)

    # Check body first to see why the status_code assertion may fail
    assert response.text == test.expected_result
    assert response.status_code == test.expected_status


@pytest.mark.parametrize(
    "test",
    find_files(TEST_DIR / "debug" / "enrich", DebugBaseline),
)
def test_debug_enrich(test: DebugBaseline, client: TestClient) -> None:
    response = client.post(
        "/debug/enrich",
        headers={"Content-Type": "application/json"},
        content=test.request,
    )

    if response.status_code == SUCCESS_CODE:
        pretty_text = prettify_json(response.text)
        print(pretty_text)
        assert pretty_text == prettify_json(test.expected_result)
    else:
        assert response.text == test.expected_result

    assert response.status_code == test.expected_status

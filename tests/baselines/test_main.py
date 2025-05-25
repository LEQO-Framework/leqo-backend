from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import BaseModel
from starlette.testclient import TestClient

from app.main import app
from tests.baselines import find_files


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


class DebugCompileBaseline(BaseModel):
    request: str
    expected_status: int
    expected_result: str


TEST_DIR = Path(__file__).parent


@pytest.mark.parametrize(
    "test",
    find_files(TEST_DIR / "debug" / "compile", DebugCompileBaseline),
)
def test_debug_compile_success(test: DebugCompileBaseline, client: TestClient) -> None:
    response = client.post(
        "/debug/compile",
        headers={"Content-Type": "application/json"},
        content=test.request,
    )

    print(response.text)

    # Check body first to see why the status_code assertion may fail
    assert response.text == test.expected_result
    assert response.status_code == test.expected_status

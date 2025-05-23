from collections.abc import Iterator
from hashlib import sha1
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel
from starlette.testclient import TestClient

from app.main import app
from app.services import NodeIdFactory, get_node_id_factory
from tests.baselines import find_files


# region service overrides
def get_dummy_node_id_factory() -> NodeIdFactory:
    def dummy_node_id_factory(node_id: str) -> UUID:
        node_id_hash = sha1(node_id.encode()).digest()
        return UUID(bytes=node_id_hash[:16])

    return dummy_node_id_factory


app.dependency_overrides[get_node_id_factory] = get_dummy_node_id_factory
# endregion


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

from collections.abc import AsyncGenerator, Iterator
from http import HTTPStatus

import pytest
from starlette.testclient import TestClient

from app.algorithm_selection.nisq_client import NisqAnalyzerClient
from app.algorithm_selection.router import get_nisq_analyzer_client
from app.main import app
from tests.algorithm_selection.fake_nisq_analyzer import BASE_URL, FakeNisqAnalyzer

QUBO = {
    "matrix": [[-1, 2, 0, 0], [0, -1, 2, 0], [0, 0, -1, 2], [0, 0, 0, -1]],
    "variables": ["router-a", "router-b", "router-c", "router-d"],
}


@pytest.fixture
def client() -> Iterator[TestClient]:
    async def fake_client() -> AsyncGenerator[NisqAnalyzerClient]:
        yield NisqAnalyzerClient(
            BASE_URL, http_client=FakeNisqAnalyzer().client(), poll_interval=0
        )

    app.dependency_overrides[get_nisq_analyzer_client] = fake_client
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_algorithm_selection_round_trip(client: TestClient) -> None:
    response = client.post("/qubo/algorithm-selection", json=QUBO)
    assert response.status_code == HTTPStatus.OK
    result = response.json()

    # Small QUBO: the size rule prefers VQE, L=1 has the lowest error chance
    assert result["selected_algorithm"] == "VQE"
    assert result["selected_layers"] == 1
    assert result["fallback_used"] is False
    assert result["selected_qpu"]["qpu"] == "ibmq_athens"
    assert result["qubit_variables"] == QUBO["variables"]
    assert result["generated_qasm"].startswith("OPENQASM 2.0;")
    assert {(c["algorithm"], c["layers"]) for c in result["candidates"]} == {
        ("QAOA", 1),
        ("QAOA", 2),
        ("VQE", 1),
        ("VQE", 2),
    }
    assert set(result["scores"]) == {"QAOA p=1", "QAOA p=2", "VQE L=1", "VQE L=2"}
    assert result["excluded_candidates"] == {}

    record_id = result["record_id"]
    stored = client.get(f"/qubo/algorithm-selection/{record_id}").json()
    assert stored["selected_algorithm"] == "VQE"
    assert stored["selected_layers"] == 1
    assert stored["selected_qpu"] == "ibmq_athens"
    assert stored["generated_qasm"] == result["generated_qasm"]
    assert stored["reasoning"] == result["reasoning"]
    assert stored["succeeded"] is None
    assert stored["candidate_qualities"] == {}

    outcome = client.put(
        f"/qubo/algorithm-selection/{record_id}/outcome",
        json={"succeeded": True, "quality": 0.8},
    )
    assert outcome.status_code == HTTPStatus.OK
    assert outcome.json()["succeeded"] is True
    assert outcome.json()["candidate_qualities"] == {"VQE L=1": 0.8}

    history = client.get("/qubo/algorithm-selection/history", params={"limit": 500})
    assert record_id in {r["id"] for r in history.json()}

    # The reported run now counts as history for the same QUBO
    again = client.post("/qubo/algorithm-selection", json=QUBO).json()
    assert record_id in again["similar_record_ids"]
    history_signal = next(s for s in again["signals"] if s["name"] == "History")
    assert history_signal["preferred"]["label"] == "VQE L=1"


def test_invalid_qubo_is_rejected(client: TestClient) -> None:
    response = client.post("/qubo/algorithm-selection", json={"matrix": [[1, 2], [3]]})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_unknown_record(client: TestClient) -> None:
    unknown = "00000000-0000-0000-0000-000000000000"

    assert (
        client.get(f"/qubo/algorithm-selection/{unknown}").status_code
        == HTTPStatus.NOT_FOUND
    )
    assert (
        client.put(
            f"/qubo/algorithm-selection/{unknown}/outcome", json={"succeeded": False}
        ).status_code
        == HTTPStatus.NOT_FOUND
    )

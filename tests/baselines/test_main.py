import json
import os
from collections.abc import Iterator
from functools import lru_cache
from json import JSONDecodeError, dumps
from pathlib import Path
from time import sleep
from typing import Any, TypeVar

import pytest
import yaml
from httpx import Response
from pydantic import BaseModel
from starlette.testclient import TestClient

from app.config import Settings
from app.main import app

TModel = TypeVar("TModel", bound=BaseModel)

SUCCESS_CODE = 200
POLL_INTERVAL = 0.1
MAX_ATTEMPTS = 5
TEST_DIR = Path(__file__).parent
LITERAL_NODE_TYPES = {"bit", "bool", "int", "float", "array"}


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


@lru_cache
def _qiskit_compat_enabled() -> bool:
    return Settings().qiskit_compat_mode


def _collect_literal_nodes(request: str) -> tuple[set[str], set[str]]:
    payload = json.loads(request)
    literal_nodes = {
        node["id"]
        for node in payload.get("nodes", [])
        if node.get("type") in LITERAL_NODE_TYPES
    }
    used_literal_nodes = {
        edge["source"][0]
        for edge in payload.get("edges", [])
        if edge.get("source", [None])[0] in literal_nodes
    }
    return literal_nodes, used_literal_nodes


def _strip_literal_blocks(qasm: str, literal_nodes: set[str]) -> str:
    if not literal_nodes:
        return qasm

    lines = qasm.splitlines()
    output: list[str] = []
    skipping: str | None = None

    for line in lines:
        stripped = line.strip()
        if skipping is not None:
            if stripped == f"/* End node {skipping} */":
                skipping = None
            continue

        if stripped.startswith("/* Start node ") and stripped.endswith(" */"):
            node_id = stripped[len("/* Start node ") : -len(" */")]
            if node_id in literal_nodes:
                skipping = node_id
                continue

        output.append(line)

    result = "\n".join(output)
    if qasm.endswith("\n"):
        result += "\n"
    return result


def _insert_qiskit_warning(qasm: str, literal_nodes_with_consumers: set[str]) -> str:
    if not literal_nodes_with_consumers:
        return qasm

    warning = (
        "/* Qiskit compatibility warning: literal outputs from "
        f"{', '.join(sorted(literal_nodes_with_consumers))} feed other nodes; "
        "resulting circuit may be incompatible. */"
    )
    lines = qasm.splitlines()
    if not lines:
        return qasm

    insert_at = 1
    while insert_at < len(lines) and lines[insert_at].strip().startswith("include "):
        insert_at += 1

    lines.insert(insert_at, warning)
    result = "\n".join(lines)
    if qasm.endswith("\n"):
        result += "\n"
    return result


def _expected_qasm(request: str, expected: str) -> str:
    if not _qiskit_compat_enabled():
        return expected
    if not expected.lstrip().startswith("OPENQASM"):
        return expected

    literal_nodes, used_literal_nodes = _collect_literal_nodes(request)
    if not literal_nodes:
        return expected

    adjusted = _strip_literal_blocks(expected, literal_nodes)
    return _insert_qiskit_warning(adjusted, used_literal_nodes)


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

    return client.get(f"/results/{uuid}")


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


def _assert_link_header(response: Response, uuid: str) -> None:
    link_header = response.headers.get("Link")
    assert link_header is not None
    assert f"/request/{uuid}" in link_header


def _assert_request_matches(
    stored_payload: dict[str, Any], expected_payload: dict[str, Any]
) -> None:
    assert stored_payload["metadata"]["name"] == expected_payload["metadata"]["name"]
    assert (
        stored_payload["metadata"]["description"]
        == expected_payload["metadata"]["description"]
    )
    assert len(stored_payload["nodes"]) == len(expected_payload["nodes"])
    for stored_node, expected_node in zip(
        stored_payload["nodes"], expected_payload["nodes"], strict=True
    ):
        for key, value in expected_node.items():
            assert str(stored_node.get(key)) == str(value)
    assert len(stored_payload["edges"]) == len(expected_payload["edges"])
    for stored_edge, expected_edge in zip(
        stored_payload["edges"], expected_payload["edges"], strict=True
    ):
        for key, value in expected_edge.items():
            assert str(stored_edge.get(key)) == str(value)


@pytest.mark.parametrize(
    "test",
    find_files(Baseline, TEST_DIR / "compile"),
    ids=lambda test: test[0],
)
def test_compile(test: tuple[str, Baseline], client: TestClient) -> None:
    _file, base = test
    response = handle_endpoints(client, base.request, "/compile")

    expected = _expected_qasm(base.request, base.expected_result)
    assert expected == response.text
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
    expected = _expected_qasm(base.request, base.expected_result)
    assert expected == response.text
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
    expected = _expected_qasm(base.merge_request, base.merge_result)
    assert expected == response.text
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

    result_response = client.get(f"/results/{uuid}")
    assert result_response.status_code == SUCCESS_CODE
    _assert_link_header(result_response, uuid)

    overview_response = client.get("/results")
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

    filtered_response = client.get("/results", params={"status": "completed"})
    assert filtered_response.status_code == SUCCESS_CODE
    filtered = filtered_response.json()
    assert all(entry["status"] == "completed" for entry in filtered)
    filtered_matches = [entry for entry in filtered if entry["uuid"] == uuid]
    assert filtered_matches, "Filtered results did not include the created request"

    by_uuid_response = client.get(f"/results?uuid={uuid}")
    assert by_uuid_response.status_code == SUCCESS_CODE
    assert by_uuid_response.text == result_response.text
    _assert_link_header(by_uuid_response, uuid)

    stored_request = client.get(f"/request/{uuid}")
    assert stored_request.status_code == SUCCESS_CODE
    stored_payload = stored_request.json()
    expected_payload = json.loads(compile_request)
    _assert_request_matches(stored_payload, expected_payload)

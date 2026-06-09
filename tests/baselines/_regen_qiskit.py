"""One-off regen helper for compile_qiskit baselines.

Run only when the qiskit exporter output deliberately changes:

    .venv/Scripts/python.exe -m pytest tests/baselines/_regen_qiskit.py -s

Walks tests/baselines/compile_qiskit/, replays each request through the live
FastAPI app via TestClient, and rewrites the `expected_result` field with the
freshly produced text.
"""

from pathlib import Path
from time import sleep

import pytest
import yaml
from starlette.testclient import TestClient

from app.main import app

BASELINE_DIR = Path(__file__).parent / "compile_qiskit"
POLL_INTERVAL = 0.1
MAX_ATTEMPTS = 50


def _str_presenter(dumper: yaml.Dumper, data: str):
    """Emit multi-line strings as literal block scalars; leave others default."""
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


yaml.add_representer(str, _str_presenter, Dumper=yaml.SafeDumper)


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def _run_one(client: TestClient, request: str) -> str:
    resp = client.post(
        "/compile",
        headers={"Content-Type": "application/json"},
        content=request,
    )
    uuid = resp.json()["uuid"]
    for _ in range(MAX_ATTEMPTS):
        status = client.get(f"/status/{uuid}").json()["status"]
        if status == "completed":
            break
        if status == "failed":
            raise RuntimeError(f"Compilation failed for {uuid}")
        sleep(POLL_INTERVAL)
    return client.get(f"/results/{uuid}").text


def test_regenerate_qiskit_baselines(client: TestClient) -> None:
    for yml_path in sorted(BASELINE_DIR.glob("*.yml")):
        with yml_path.open() as f:
            data = yaml.safe_load(f)
        data["expected_result"] = _run_one(client, data["request"])
        with yml_path.open("w", newline="\n") as f:
            yaml.safe_dump(
                data,
                f,
                sort_keys=False,
                allow_unicode=True,
                width=10_000,
            )
        print(f"updated {yml_path.name}")

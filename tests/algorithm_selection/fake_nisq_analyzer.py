"""
In-process stand-in for the NISQ Analyzer REST API, served through :class:`httpx.MockTransport`.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

BASE_URL = "http://nisq-analyzer.test/nisq-analyzer"


@dataclass
class FakeQpu:
    name: str
    qubits: int
    single_qubit_error: float = 0.0005
    multi_qubit_error: float = 0.01
    readout_error: float = 0.02


@dataclass
class FakeNisqAnalyzer:
    """
    Compiles nothing: counts gates of the submitted OpenQASM 2 circuit and reports them per QPU.

    :param qpus: QPUs that are ranked in the given order, best first.
    :param polls_until_ready: GET requests per job that still answer ``ready: false``.
    :param ranking_state: Final state of ranking jobs.
    """

    qpus: list[FakeQpu] = field(default_factory=lambda: [FakeQpu("ibmq_athens", 5)])
    polls_until_ready: int = 1
    ranking_state: str = "FINISHED"
    requests: list[httpx.Request] = field(default_factory=list)
    _jobs: dict[str, dict[str, Any]] = field(default_factory=dict)
    _polls: dict[str, int] = field(default_factory=dict)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handle))

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path.removeprefix("/nisq-analyzer")

        if request.method == "POST" and path == "/qpu-selection":
            return self._submit(json.loads(request.content))
        if match := re.fullmatch(r"/qpu-selection-results/jobs/([\w-]+)", path):
            return self._poll(match.group(1))
        if match := re.fullmatch(r"/mcda-methods/([\w-]+)/prioritize", path):
            return self._prioritize(match.group(1), request.url.params["jobId"])
        if match := re.fullmatch(r"/mcda-methods/[\w-]+/jobs/([\w-]+)", path):
            return self._poll(match.group(1))
        return httpx.Response(404)

    def _submit(self, body: dict[str, Any]) -> httpx.Response:
        qasm: str = body["qasmCode"]
        width = int(re.search(r"qreg \w+\[(\d+)\]", qasm).group(1))
        lines = [line.strip() for line in qasm.splitlines()]
        multi = sum(1 for line in lines if line.startswith("cx "))
        measure = sum(1 for line in lines if line.startswith("measure "))
        single = sum(
            1 for line in lines if re.match(r"(h|rx|ry|rz)[ (]", line) is not None
        )

        results = [
            self._result("aer_simulator", width, single, multi, measure, 0, 0, 0, True)
        ]
        results.extend(
            self._result(
                qpu.name,
                width,
                single,
                multi,
                measure,
                qpu.single_qubit_error,
                qpu.multi_qubit_error,
                qpu.readout_error,
                False,
            )
            for qpu in self.qpus
            if qpu.qubits >= width
        )
        job_id = str(uuid.uuid4())
        self._jobs[job_id] = {
            "id": job_id,
            "circuitName": body["circuitName"],
            "ready": True,
            "qpuSelectionResultList": results,
        }
        return httpx.Response(
            200, json={"id": job_id, "ready": False, "qpuSelectionResultList": []}
        )

    def _prioritize(self, method: str, job_id: str) -> httpx.Response:
        results = self._jobs[job_id]["qpuSelectionResultList"]
        ranking_id = str(uuid.uuid4())
        self._jobs[ranking_id] = {
            "id": ranking_id,
            "method": method,
            "state": self.ranking_state,
            "ready": True,
            "rankedResults": [
                {"resultId": r["id"], "position": i + 1, "score": 1 - i / len(results)}
                for i, r in enumerate(results)
            ]
            if self.ranking_state == "FINISHED"
            else None,
        }
        return httpx.Response(
            200, json={"id": ranking_id, "state": "INITIALIZED", "ready": False}
        )

    def _poll(self, job_id: str) -> httpx.Response:
        if job_id not in self._jobs:
            return httpx.Response(404)
        self._polls[job_id] = self._polls.get(job_id, 0) + 1
        if self._polls[job_id] <= self.polls_until_ready:
            return httpx.Response(200, json={"id": job_id, "ready": False})
        return httpx.Response(200, json=self._jobs[job_id])

    @staticmethod
    def _result(  # noqa: PLR0913
        qpu: str,
        width: int,
        single: int,
        multi: int,
        measure: int,
        single_error: float,
        multi_error: float,
        readout_error: float,
        simulator: bool,
    ) -> dict[str, Any]:
        return {
            "id": str(uuid.uuid4()),
            "provider": "ibmq",
            "qpu": qpu,
            "compiler": "qiskit",
            "analyzedDepth": single + multi,
            "analyzedWidth": width,
            "analyzedNumberOfSingleQubitGates": single,
            "analyzedNumberOfMultiQubitGates": multi,
            "analyzedNumberOfMeasurementOperations": measure,
            "avgSingleQubitGateError": single_error,
            "avgMultiQubitGateError": multi_error,
            "avgReadoutError": readout_error,
            "t1": 0.0 if simulator else 57600.0,
            "t2": 0.0 if simulator else 60000.0,
            "simulator": simulator,
            "transpiledCircuit": "OPENQASM 2.0;",
        }

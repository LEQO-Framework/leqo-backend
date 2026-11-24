"""
Async client for the QPU selection workflow of the NISQ Analyzer.

The workflow of the NISQ Analyzer is:

1. ``POST /qpu-selection`` submits an OpenQASM circuit and returns a job.
2. ``GET /qpu-selection-results/jobs/{id}`` is polled until ``ready``.
   The job then lists one compiled circuit per suitable QPU and compiler, plus the simulator.
3. ``POST /mcda-methods/{method}/prioritize?jobId={id}`` ranks these results and returns a ranking job.
4. ``GET /mcda-methods/{method}/jobs/{id}`` is polled until ``ready``; ``rankedResults`` holds the ranking.
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Callable, Sequence
from typing import Any, Self

import httpx

from app.algorithm_selection.models import QPUSelection

JsonObject = dict[str, Any]


class NisqAnalyzerError(Exception):
    """
    The NISQ Analyzer could not produce a QPU ranking.
    """


class NoSuitableQpuError(NisqAnalyzerError):
    """
    The NISQ Analyzer found no real QPU that can execute the circuit.
    """


def estimate_success_probability(result: JsonObject) -> float | None:
    """
    Estimate the probability that a compiled circuit runs without any error.

    Estimated success probability (ESP, Nishio et al. 2020): the product of the success rates
    of all gates and measurements.
    The NISQ Analyzer reports averaged error rates per QPU, so the averages are used:
    ``ESP = (1 - e_1q)^n_1q * (1 - e_2q)^n_2q * (1 - e_ro)^n_meas``.

    :param result: A ``QpuSelectionResultDto`` of the NISQ Analyzer.
    :return: The ESP or None if the QPU lacks error rates.
    """

    pairs = (
        ("avgSingleQubitGateError", "analyzedNumberOfSingleQubitGates"),
        ("avgMultiQubitGateError", "analyzedNumberOfMultiQubitGates"),
        ("avgReadoutError", "analyzedNumberOfMeasurementOperations"),
    )
    log_probability = 0.0
    for error_key, count_key in pairs:
        error = result.get(error_key)
        count = result.get(count_key)
        if error is None or count is None or not 0 <= error <= 1:
            return None
        if count == 0:
            continue
        if error == 1:
            return 0.0
        log_probability += count * math.log1p(-error)
    return math.exp(log_probability)


class NisqAnalyzerClient:
    """
    Submits circuits to the NISQ Analyzer and returns the top-ranked real QPU.
    """

    def __init__(  # noqa: PLR0913
        self,
        base_url: str,
        *,
        mcda_method: str = "topsis",
        allowed_providers: Sequence[str] = ("ibmq",),
        compilers: Sequence[str] = ("qiskit",),
        tokens: dict[str, dict[str, str]] | None = None,
        poll_interval: float = 3.0,
        timeout: float = 600.0,
        http_client: httpx.AsyncClient | None = None,
    ):
        """
        :param base_url: Base URL of the NISQ Analyzer.
        :param mcda_method: ``topsis``, ``promethee-II`` or ``electre-III``.
        :param allowed_providers: Providers whose QPUs are considered.
        :param compilers: Compilers used to compile the circuit for each QPU.
        :param tokens: Provider tokens forwarded to the compiler services.
        :param poll_interval: Seconds between two polls of a job.
        :param timeout: Maximum seconds to wait for one job.
        :param http_client: Client to use. The client is owned by the caller if given.
        """

        self.mcda_method = mcda_method
        self.allowed_providers = list(allowed_providers)
        self.compilers = list(compilers)
        self.tokens = tokens if tokens is not None else {}
        self.poll_interval = poll_interval
        self.timeout = timeout
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(timeout=60.0)
        self._base_url = base_url.rstrip("/")

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def select_qpu(self, qasm: str, circuit_name: str) -> QPUSelection:
        """
        Run QPU selection and MCDA ranking for an OpenQASM 2 circuit.

        :param qasm: The circuit.
        :param circuit_name: Name of the circuit in the NISQ Analyzer.
        :return: The top-ranked real QPU with its error rates and error chance.
        :raises NoSuitableQpuError: If no real QPU can execute the circuit.
        :raises NisqAnalyzerError: If a job fails, times out or a request fails.
        """

        job = await self._request(
            "POST",
            "/qpu-selection",
            json={
                "circuitLanguage": "openqasm",
                "qasmCode": qasm,
                "circuitName": circuit_name,
                "allowedProviders": self.allowed_providers,
                "compilers": self.compilers,
                "tokens": self.tokens,
                "preciseResultsPreference": False,
                "shortWaitingTimesPreference": False,
                "queueImportanceRatio": 0,
                "maxNumberOfCompiledCircuits": 0,
            },
        )
        job_id = _require(job, "id")
        job = await self._poll(
            f"/qpu-selection-results/jobs/{job_id}", lambda j: bool(j.get("ready"))
        )

        results: list[JsonObject] = job.get("qpuSelectionResultList") or []
        if not any(not r.get("simulator", False) for r in results):
            msg = (
                f"No QPU of the providers {self.allowed_providers} can execute "
                f"circuit '{circuit_name}'."
            )
            raise NoSuitableQpuError(msg)

        ranking_job = await self._request(
            "POST",
            f"/mcda-methods/{self.mcda_method}/prioritize",
            params={
                "jobId": job_id,
                "useBordaCount": "false",
                "queueImportanceRatio": "0",
            },
        )
        ranking_job_id = _require(ranking_job, "id")
        ranking_job = await self._poll(
            f"/mcda-methods/{self.mcda_method}/jobs/{ranking_job_id}",
            lambda j: bool(j.get("ready")) or j.get("state") == "FAILED",
        )
        if ranking_job.get("state") != "FINISHED":
            msg = f"MCDA ranking job {ranking_job_id} ended in state {ranking_job.get('state')}."
            raise NisqAnalyzerError(msg)

        by_id = {r["id"]: r for r in results}
        ranking = sorted(
            ranking_job.get("rankedResults") or [], key=lambda r: r["position"]
        )
        for ranked in ranking:
            result = by_id.get(ranked["resultId"])
            if result is not None and not result.get("simulator", False):
                return _to_qpu_selection(result, ranked, self.mcda_method)

        msg = f"MCDA ranking job {ranking_job_id} ranked no real QPU."
        raise NisqAnalyzerError(msg)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: JsonObject | None = None,
        params: dict[str, str] | None = None,
    ) -> JsonObject:
        try:
            response = await self._client.request(
                method,
                f"{self._base_url}{path}",
                json=json,
                params=params,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
        except httpx.HTTPError as ex:
            msg = f"NISQ Analyzer request {method} {path} failed: {ex}"
            raise NisqAnalyzerError(msg) from ex

        body = response.json()
        if not isinstance(body, dict):
            msg = f"NISQ Analyzer returned no JSON object for {method} {path}."
            raise NisqAnalyzerError(msg)
        return body

    async def _poll(self, path: str, done: Callable[[JsonObject], bool]) -> JsonObject:
        try:
            async with asyncio.timeout(self.timeout):
                while True:
                    body = await self._request("GET", path)
                    if done(body):
                        return body
                    await asyncio.sleep(self.poll_interval)
        except TimeoutError as ex:
            msg = f"NISQ Analyzer job {path} not ready after {self.timeout} s."
            raise NisqAnalyzerError(msg) from ex


def _require(body: JsonObject, key: str) -> Any:
    value = body.get(key)
    if value is None:
        msg = f"NISQ Analyzer response lacks '{key}'."
        raise NisqAnalyzerError(msg)
    return value


def _to_qpu_selection(
    result: JsonObject, ranked: JsonObject, mcda_method: str
) -> QPUSelection:
    success_probability = estimate_success_probability(result)
    return QPUSelection(
        provider=result["provider"],
        qpu=result["qpu"],
        compiler=result["compiler"],
        mcda_method=mcda_method,
        mcda_position=ranked["position"],
        mcda_score=ranked.get("score"),
        analyzed_depth=result.get("analyzedDepth", 0),
        analyzed_width=result.get("analyzedWidth", 0),
        number_of_single_qubit_gates=result.get("analyzedNumberOfSingleQubitGates", 0),
        number_of_multi_qubit_gates=result.get("analyzedNumberOfMultiQubitGates", 0),
        number_of_measurement_operations=result.get(
            "analyzedNumberOfMeasurementOperations", 0
        ),
        avg_single_qubit_gate_error=result.get("avgSingleQubitGateError"),
        avg_multi_qubit_gate_error=result.get("avgMultiQubitGateError"),
        avg_readout_error=result.get("avgReadoutError"),
        t1=result.get("t1"),
        t2=result.get("t2"),
        transpiled_circuit=result.get("transpiledCircuit"),
        estimated_success_probability=success_probability,
        error_chance=None if success_probability is None else 1 - success_probability,
    )

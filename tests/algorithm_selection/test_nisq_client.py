import math

import httpx
import pytest

from app.algorithm_selection.nisq_client import (
    NisqAnalyzerClient,
    NisqAnalyzerError,
    NoSuitableQpuError,
    estimate_success_probability,
)
from tests.algorithm_selection.fake_nisq_analyzer import (
    BASE_URL,
    FakeNisqAnalyzer,
    FakeQpu,
)

BELL = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg meas[2];
h q[0];
cx q[0],q[1];
measure q[0] -> meas[0];
measure q[1] -> meas[1];
"""


def client(analyzer: FakeNisqAnalyzer, **kwargs) -> NisqAnalyzerClient:
    return NisqAnalyzerClient(
        BASE_URL, http_client=analyzer.client(), poll_interval=0, **kwargs
    )


def test_estimate_success_probability() -> None:
    result = {
        "avgSingleQubitGateError": 0.001,
        "analyzedNumberOfSingleQubitGates": 10,
        "avgMultiQubitGateError": 0.01,
        "analyzedNumberOfMultiQubitGates": 5,
        "avgReadoutError": 0.02,
        "analyzedNumberOfMeasurementOperations": 2,
    }
    expected = 0.999**10 * 0.99**5 * 0.98**2

    assert estimate_success_probability(result) == pytest.approx(expected)


def test_estimate_success_probability_without_error_rates() -> None:
    assert estimate_success_probability({"avgSingleQubitGateError": None}) is None


@pytest.mark.asyncio
async def test_select_qpu_follows_the_nisq_analyzer_workflow() -> None:
    analyzer = FakeNisqAnalyzer(
        qpus=[FakeQpu("ibmq_athens", 5), FakeQpu("ibmq_valencia", 5)],
        polls_until_ready=2,
    )

    async with client(analyzer, mcda_method="promethee-II") as nisq:
        selection = await nisq.select_qpu(BELL, "bell")

    calls = [
        (r.method, r.url.path.removeprefix("/nisq-analyzer")) for r in analyzer.requests
    ]
    assert calls[0] == ("POST", "/qpu-selection")
    assert calls.count(("POST", "/mcda-methods/promethee-II/prioritize")) == 1
    # Each job is polled until it is ready
    assert len([c for c in calls if c[0] == "GET"]) == len(["selection", "ranking"]) * (
        analyzer.polls_until_ready + 1
    )

    submitted = analyzer.requests[0]
    assert b'"qasmCode"' in submitted.content
    prioritize = next(r for r in analyzer.requests if "prioritize" in r.url.path)
    assert prioritize.url.params["useBordaCount"] == "false"

    # The simulator ranks first but is skipped
    assert selection.qpu == "ibmq_athens"
    assert selection.mcda_position == len(["aer_simulator", "ibmq_athens"])
    assert selection.number_of_multi_qubit_gates == 1
    expected_success = (1 - 0.0005) * (1 - 0.01) * (1 - 0.02) ** 2
    assert selection.estimated_success_probability == pytest.approx(expected_success)
    assert selection.error_chance == pytest.approx(1 - expected_success)


@pytest.mark.asyncio
async def test_select_qpu_without_suitable_qpu() -> None:
    analyzer = FakeNisqAnalyzer(qpus=[FakeQpu("ibmq_tiny", 1)])

    with pytest.raises(NoSuitableQpuError):
        await client(analyzer).select_qpu(BELL, "bell")

    assert not any("prioritize" in r.url.path for r in analyzer.requests)


@pytest.mark.asyncio
async def test_select_qpu_with_failed_ranking() -> None:
    analyzer = FakeNisqAnalyzer(ranking_state="FAILED")

    with pytest.raises(NisqAnalyzerError, match="FAILED"):
        await client(analyzer).select_qpu(BELL, "bell")


@pytest.mark.asyncio
async def test_select_qpu_times_out() -> None:
    analyzer = FakeNisqAnalyzer(polls_until_ready=math.inf)

    with pytest.raises(NisqAnalyzerError, match="not ready"):
        await client(analyzer, timeout=0.05).select_qpu(BELL, "bell")


@pytest.mark.asyncio
async def test_select_qpu_with_unreachable_analyzer() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(refuse))
    nisq = NisqAnalyzerClient(BASE_URL, http_client=http_client)

    with pytest.raises(NisqAnalyzerError, match="connection refused"):
        await nisq.select_qpu(BELL, "bell")

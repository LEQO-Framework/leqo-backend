import pytest
from openqasm3.ast import Identifier, Program, QuantumMeasurementStatement
from pydantic import ValidationError

from app.algorithm_selection.models import Candidate, QuantumAlgorithm, QUBOProblem
from app.algorithm_selection.nisq_client import NisqAnalyzerClient
from app.algorithm_selection.qasm_service import (
    ALGORITHM_IMPLEMENTATIONS,
    QuboCircuitService,
    UnsupportedCircuitError,
    program_to_qasm2,
)
from tests.algorithm_selection.fake_nisq_analyzer import (
    BASE_URL,
    FakeNisqAnalyzer,
    FakeQpu,
)

CHAIN_VARIABLES = 4
CHAIN_COUPLINGS = 3

CHAIN_QUBO = QUBOProblem(
    matrix=[
        [-1, 2, 0, 0],
        [0, -1, 2, 0],
        [0, 0, -1, 2],
        [0, 0, 0, -1],
    ]
)


def count(qasm: str, prefix: str) -> int:
    return sum(1 for line in qasm.splitlines() if line.startswith(prefix))


def test_qubo_features() -> None:
    qubo = QUBOProblem(matrix=[[1, 1, 0], [-1, 0, 2], [0, 0, 3]])

    # Q[0][1] + Q[1][0] = 0 cancels out
    assert qubo.couplings == {(1, 2): 2.0}
    assert qubo.density == pytest.approx(1 / 3)
    assert qubo.coupled_variables == [1, 2]
    assert qubo.variable_names == ["x0", "x1", "x2"]


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"matrix": [[1, 2], [3]]}, "must be square"),
        ({"matrix": [[1, 0], [0, 1]]}, "no quadratic couplings"),
        ({"matrix": [[1, 1], [0, 1]], "variables": ["a"]}, "Expected 2 variable names"),
        ({"matrix": [[1, 1], [0, 1]], "variables": ["a", "a"]}, "must be unique"),
        ({"matrix": [[1]]}, "at least 2"),
    ],
)
def test_qubo_validation(payload: dict, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        QUBOProblem.model_validate(payload)


def test_every_qubo_algorithm_has_an_implementation() -> None:
    assert set(ALGORITHM_IMPLEMENTATIONS) == set(QuantumAlgorithm)


@pytest.mark.asyncio
async def test_qaoa_circuit_has_one_zz_interaction_per_coupling() -> None:
    service = QuboCircuitService(
        NisqAnalyzerClient(BASE_URL, http_client=FakeNisqAnalyzer().client())
    )
    layers = 2
    circuit = await service.generate(
        CHAIN_QUBO, Candidate(algorithm=QuantumAlgorithm.QAOA, layers=layers)
    )

    assert circuit.width == CHAIN_VARIABLES
    assert "qreg q[4];" in circuit.qasm
    assert count(circuit.qasm, "cx ") == CHAIN_COUPLINGS * 2 * layers
    # Local fields h_i = 1/2 - deg(i)/2 vanish at both chain ends
    assert count(circuit.qasm, "rz(") == (CHAIN_COUPLINGS + 2) * layers
    assert count(circuit.qasm, "rx(") == CHAIN_VARIABLES * layers
    assert count(circuit.qasm, "measure ") == CHAIN_VARIABLES


@pytest.mark.asyncio
async def test_vqe_circuit_uses_hardware_efficient_ansatz() -> None:
    layers = 3
    service = QuboCircuitService(
        NisqAnalyzerClient(BASE_URL, http_client=FakeNisqAnalyzer().client())
    )
    circuit = await service.generate(
        CHAIN_QUBO, Candidate(algorithm=QuantumAlgorithm.VQE, layers=layers)
    )

    assert circuit.width == CHAIN_VARIABLES
    assert count(circuit.qasm, "cx ") == (CHAIN_VARIABLES - 1) * layers
    assert count(circuit.qasm, "ry(") == CHAIN_VARIABLES * (layers + 1)


@pytest.mark.asyncio
async def test_uncoupled_variables_need_no_qubits() -> None:
    # x0 and x3 only have linear terms
    qubo = QUBOProblem(matrix=[[-1, 0, 0, 0], [0, 0, 1, 0], [0, 0, 0, 0], [0, 0, 0, 5]])
    service = QuboCircuitService(
        NisqAnalyzerClient(BASE_URL, http_client=FakeNisqAnalyzer().client())
    )

    for candidate in service.candidates:
        circuit = await service.generate(qubo, candidate)
        assert circuit.width == len(qubo.coupled_variables)
        assert "qreg q[2];" in circuit.qasm


@pytest.mark.asyncio
async def test_analyze_passes_all_circuits_to_the_nisq_analyzer() -> None:
    analyzer = FakeNisqAnalyzer()
    service = QuboCircuitService(
        NisqAnalyzerClient(BASE_URL, http_client=analyzer.client(), poll_interval=0)
    )

    evaluations = await service.analyze(CHAIN_QUBO)

    assert [e.algorithm for e in evaluations] == list(QuantumAlgorithm)
    for evaluation in evaluations:
        assert evaluation.nisq_reachable
        assert evaluation.qpu_selection is not None
        assert evaluation.qpu_selection.qpu == "ibmq_athens"
    submitted = [r for r in analyzer.requests if r.url.path.endswith("/qpu-selection")]
    assert len(submitted) == len(QuantumAlgorithm)


@pytest.mark.asyncio
async def test_analyze_reports_circuits_without_suitable_qpu() -> None:
    analyzer = FakeNisqAnalyzer(qpus=[FakeQpu("ibmq_athens", 3)])
    service = QuboCircuitService(
        NisqAnalyzerClient(BASE_URL, http_client=analyzer.client(), poll_interval=0)
    )

    evaluations = await service.analyze(CHAIN_QUBO)

    for evaluation in evaluations:
        assert evaluation.nisq_reachable
        assert evaluation.qpu_selection is None
        assert "No QPU" in (evaluation.nisq_error or "")


def test_program_to_qasm2_rejects_unsupported_statements() -> None:
    program = Program(
        [QuantumMeasurementStatement(Identifier("q"), None)], version="3.1"
    )
    with pytest.raises(UnsupportedCircuitError, match="QuantumMeasurementStatement"):
        program_to_qasm2(program)


@pytest.mark.asyncio
async def test_analyze_submits_every_candidate() -> None:
    candidates = [
        Candidate(algorithm=algorithm, layers=layers)
        for algorithm in QuantumAlgorithm
        for layers in (1, 2)
    ]
    analyzer = FakeNisqAnalyzer()
    service = QuboCircuitService(
        NisqAnalyzerClient(BASE_URL, http_client=analyzer.client(), poll_interval=0),
        candidates,
    )

    evaluations = await service.analyze(CHAIN_QUBO)

    assert [e.candidate for e in evaluations] == candidates
    names = {
        r.read().decode()
        for r in analyzer.requests
        if r.url.path.endswith("/qpu-selection")
    }
    assert len(names) == len(candidates)
    # Deeper circuits have more CNOTs and thus a higher error chance.
    chances = {
        e.candidate.label: e.qpu_selection.error_chance
        for e in evaluations
        if e.qpu_selection
    }
    assert chances["QAOA p=1"] < chances["QAOA p=2"]
    assert chances["VQE L=1"] < chances["VQE L=2"]


def test_service_needs_a_candidate() -> None:
    with pytest.raises(ValueError, match="At least one candidate"):
        QuboCircuitService(NisqAnalyzerClient(BASE_URL), [])

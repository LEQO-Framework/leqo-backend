"""
Pydantic models of the QUBO algorithm selection workflow.
"""

from __future__ import annotations

import math
from datetime import datetime
from enum import StrEnum
from functools import cached_property
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

MIN_QUBO_VARIABLES = 2


class QuantumAlgorithm(StrEnum):
    """
    Quantum algorithms that can solve a QUBO with the implementations of this project.
    """

    QAOA = "QAOA"
    VQE = "VQE"


class Candidate(BaseModel):
    """
    An algorithm with the depth of its circuit: one option of the algorithm selection.
    """

    model_config = ConfigDict(use_attribute_docstrings=True, frozen=True)

    algorithm: QuantumAlgorithm
    layers: int = Field(gt=0)
    """QAOA layers ``p`` or hardware-efficient ansatz layers ``L`` of the VQE."""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def label(self) -> str:
        """Readable name such as ``QAOA p=2`` or ``VQE L=1``."""

        depth = "p" if self.algorithm == QuantumAlgorithm.QAOA else "L"
        return f"{self.algorithm} {depth}={self.layers}"

    def __str__(self) -> str:
        return self.label


class QUBOProblem(BaseModel):
    """
    Quadratic unconstrained binary optimization problem
    ``min x^T Q x + offset`` with ``x`` in ``{0, 1}^n``.
    """

    model_config = ConfigDict(use_attribute_docstrings=True, frozen=True)

    matrix: list[list[float]] = Field(min_length=MIN_QUBO_VARIABLES)
    """Square QUBO matrix Q. Q[i][j] and Q[j][i] together form the coupling of x_i and x_j."""

    variables: list[str] | None = None
    """Optional names of the binary variables, defaults to x0 ... x(n-1)."""

    offset: float = 0.0
    """Constant energy offset."""

    @model_validator(mode="after")
    def _validate_matrix(self) -> QUBOProblem:
        n = len(self.matrix)
        for index, row in enumerate(self.matrix):
            if len(row) != n:
                msg = f"QUBO matrix must be square: row {index} has {len(row)} entries, expected {n}."
                raise ValueError(msg)
            if not all(math.isfinite(value) for value in row):
                msg = f"QUBO matrix row {index} contains non-finite values."
                raise ValueError(msg)

        if self.variables is not None:
            if len(self.variables) != n:
                msg = f"Expected {n} variable names, got {len(self.variables)}."
                raise ValueError(msg)
            if len(set(self.variables)) != n:
                msg = "Variable names must be unique."
                raise ValueError(msg)

        if not self.couplings:
            msg = "QUBO has no quadratic couplings."
            raise ValueError(msg)
        return self

    @property
    def num_variables(self) -> int:
        return len(self.matrix)

    @property
    def variable_names(self) -> list[str]:
        if self.variables is not None:
            return list(self.variables)
        return [f"x{i}" for i in range(self.num_variables)]

    @cached_property
    def couplings(self) -> dict[tuple[int, int], float]:
        """
        Non-zero quadratic couplings ``(i, j) -> Q[i][j] + Q[j][i]`` with ``i < j``.
        """

        n = self.num_variables
        result: dict[tuple[int, int], float] = {}
        for i in range(n):
            for j in range(i + 1, n):
                weight = self.matrix[i][j] + self.matrix[j][i]
                if weight != 0:
                    result[(i, j)] = weight
        return result

    @property
    def density(self) -> float:
        """
        Number of couplings normalized by its maximum ``n(n-1)/2``.
        """

        n = self.num_variables
        return len(self.couplings) / (n * (n - 1) / 2)

    @property
    def field_coupling_ratio(self) -> float:
        """
        Mean absolute local field over mean absolute coupling of the Ising form.

        With ``x = (1 - z) / 2`` the QUBO equals ``sum J_ij z_i z_j + sum h_i z_i`` up to a constant,
        where ``J_ij = w_ij / 4`` and ``h_i = -Q_ii / 2 - sum_j w_ij / 4`` for the couplings
        ``w_ij = Q_ij + Q_ji``.
        """

        fields = [-self.matrix[i][i] / 2 for i in range(self.num_variables)]
        for (i, j), weight in self.couplings.items():
            fields[i] -= weight / 4
            fields[j] -= weight / 4
        mean_field = sum(abs(h) for h in fields) / len(fields)
        mean_coupling = sum(abs(w) / 4 for w in self.couplings.values()) / len(
            self.couplings
        )
        return mean_field / mean_coupling

    @property
    def coupled_variables(self) -> list[int]:
        """
        Sorted indices of all variables that take part in at least one coupling.

        Only these need qubits: uncoupled variables are optimized independently.
        """

        return sorted({index for pair in self.couplings for index in pair})


class QPUSelection(BaseModel):
    """
    Top-ranked real QPU for a circuit, as ranked by the NISQ Analyzer.
    """

    provider: str
    qpu: str
    compiler: str
    mcda_method: str
    mcda_position: int
    mcda_score: float | None
    analyzed_depth: int
    analyzed_width: int
    number_of_single_qubit_gates: int
    number_of_multi_qubit_gates: int
    number_of_measurement_operations: int
    avg_single_qubit_gate_error: float | None
    avg_multi_qubit_gate_error: float | None
    avg_readout_error: float | None
    t1: float | None
    t2: float | None
    transpiled_circuit: str | None
    estimated_success_probability: float | None
    """Product of the success rates of all gates and measurements of the compiled circuit."""

    error_chance: float | None
    """``1 - estimated_success_probability``."""


class CandidateEvaluation(BaseModel):
    """
    Circuit generated for one candidate and its NISQ Analyzer result.
    """

    algorithm: QuantumAlgorithm
    layers: int
    qasm: str
    width: int
    qpu_selection: QPUSelection | None = None
    nisq_error: str | None = None
    """Why the NISQ Analyzer gave no QPU for this circuit, if it did not."""

    nisq_reachable: bool = False
    """Whether the NISQ Analyzer analyzed the circuit (even without a suitable QPU)."""

    @property
    def candidate(self) -> Candidate:
        return Candidate(algorithm=self.algorithm, layers=self.layers)


class SignalResult(BaseModel):
    """
    Vote of one decision signal.
    """

    name: str
    weight: float
    preferred: Candidate | None
    explanation: str


class AlgorithmSelectionResult(BaseModel):
    """
    Result of the QUBO algorithm selection workflow.
    """

    record_id: UUID
    selected_algorithm: QuantumAlgorithm
    selected_layers: int
    fallback_used: bool
    """True if no signal gave a clear result and the shallowest feasible VQE was selected."""

    scores: dict[str, float]
    """Summed signal weights per feasible candidate label."""

    excluded_candidates: dict[str, str]
    """Candidates removed by the NISQ Analyzer filter, with the reason, per label."""

    signals: list[SignalResult]
    reasoning: str
    generated_qasm: str
    selected_qpu: QPUSelection | None
    qubit_variables: list[str]
    """Variable represented by each qubit of the generated circuit."""

    candidates: list[CandidateEvaluation]
    similar_record_ids: list[UUID]


class ExecutionOutcome(BaseModel):
    """
    Reported outcome of solving a QUBO with the selected algorithm.
    """

    succeeded: bool
    quality: float | None = Field(default=None, ge=0, le=1)
    """Solution quality of the selected candidate, higher is better (e.g. the approximation
    ratio); without it, a success counts as 1 and a failure as 0."""


class ExecutionRecordResponse(BaseModel):
    """
    Public view of a stored :class:`~app.model.database_model.ExecutionRecord`.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    input_qubo: dict[str, object]
    num_variables: int
    density: float
    variable_names: list[str]
    selected_algorithm: QuantumAlgorithm
    selected_layers: int
    generated_qasm: str
    selected_qpu: str | None
    selected_provider: str | None
    error_chance: float | None
    reasoning: str
    succeeded: bool | None
    candidate_qualities: dict[str, float]

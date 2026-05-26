import pytest
from openqasm3.ast import QuantumGate
from sqlalchemy.ext.asyncio import AsyncEngine

from app.enricher import Constraints
from app.enricher.operator import OperatorEnricherStrategy
from app.model.CompileRequest import OperatorNode
from app.model.data_types import FloatType, QubitType
from app.model.exceptions import (
    InputCountMismatch,
    InputSizeMismatch,
    InputTypeMismatch,
)

EXPECTED_WIDTH = 3
EXPECTED_MIN_DEPTH = 1
EXPECTED_MAX_DEPTH = 3
SINGLE_QUBIT_SIZE = 1
INVALID_REGISTER_SIZE = 2


def _only_quantum_gates(statements: list[object]) -> list[QuantumGate]:
    return [stmt for stmt in statements if isinstance(stmt, QuantumGate)]


@pytest.mark.asyncio
async def test_dynamic_quantum_min_generates_ccx_gate(
    engine: AsyncEngine,
) -> None:
    node = OperatorNode(id="min_1", type="operator", operator="min")
    constraints = Constraints(
        requested_inputs={
            0: QubitType(size=SINGLE_QUBIT_SIZE),
            1: QubitType(size=SINGLE_QUBIT_SIZE),
        },
        requested_input_values={},
    )

    strategy = OperatorEnricherStrategy(engine)

    results = await strategy._enrich_impl(node, constraints)

    assert len(results) == 1

    result = results[0]
    statements = result.enriched_node.implementation.statements
    gates = _only_quantum_gates(statements)

    assert result.meta_data.width == EXPECTED_WIDTH
    assert result.meta_data.depth == EXPECTED_MIN_DEPTH
    assert [gate.name.name for gate in gates] == ["ccx"]


def test_dynamic_quantum_min_requires_two_inputs(engine: AsyncEngine) -> None:
    node = OperatorNode(id="min_1", type="operator", operator="min")
    constraints = Constraints(
        requested_inputs={0: QubitType(size=SINGLE_QUBIT_SIZE)},
        requested_input_values={},
    )

    strategy = OperatorEnricherStrategy(engine)

    with pytest.raises(InputCountMismatch):
        strategy._generate_min_enrichment(node, constraints)


def test_dynamic_quantum_min_requires_qubit_inputs(engine: AsyncEngine) -> None:
    node = OperatorNode(id="min_1", type="operator", operator="min")
    constraints = Constraints(
        requested_inputs={
            0: QubitType(size=SINGLE_QUBIT_SIZE),
            1: FloatType(size=32),
        },
        requested_input_values={},
    )

    strategy = OperatorEnricherStrategy(engine)

    with pytest.raises(InputTypeMismatch):
        strategy._generate_min_enrichment(node, constraints)


def test_dynamic_quantum_min_rejects_multi_qubit_registers(
    engine: AsyncEngine,
) -> None:
    node = OperatorNode(id="min_1", type="operator", operator="min")
    constraints = Constraints(
        requested_inputs={
            0: QubitType(size=INVALID_REGISTER_SIZE),
            1: QubitType(size=SINGLE_QUBIT_SIZE),
        },
        requested_input_values={},
    )

    strategy = OperatorEnricherStrategy(engine)

    with pytest.raises(InputSizeMismatch):
        strategy._generate_min_enrichment(node, constraints)


@pytest.mark.asyncio
async def test_dynamic_quantum_max_generates_or_gate_pattern(
    engine: AsyncEngine,
) -> None:
    node = OperatorNode(id="max_1", type="operator", operator="max")
    constraints = Constraints(
        requested_inputs={
            0: QubitType(size=SINGLE_QUBIT_SIZE),
            1: QubitType(size=SINGLE_QUBIT_SIZE),
        },
        requested_input_values={},
    )

    strategy = OperatorEnricherStrategy(engine)

    results = await strategy._enrich_impl(node, constraints)

    assert len(results) == 1

    result = results[0]
    statements = result.enriched_node.implementation.statements
    gates = _only_quantum_gates(statements)

    assert result.meta_data.width == EXPECTED_WIDTH
    assert result.meta_data.depth == EXPECTED_MAX_DEPTH
    assert [gate.name.name for gate in gates] == ["cx", "cx", "ccx"]

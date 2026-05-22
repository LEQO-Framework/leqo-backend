import pytest
from openqasm3.ast import QuantumGate

from app.enricher import Constraints
from app.enricher.operator import OperatorEnricherStrategy
from app.model.CompileRequest import OperatorNode
from app.model.data_types import QubitType
from app.model.exceptions import InputCountMismatch, InputTypeMismatch

REGISTER_SIZE = 3
EXPECTED_DEPTH = 1
EXPECTED_GATE_COUNT = 3


def _only_quantum_gates(statements):
    return [stmt for stmt in statements if isinstance(stmt, QuantumGate)]


@pytest.mark.asyncio
async def test_dynamic_quantum_bitwise_not_generates_x_gates(engine) -> None:
    node = OperatorNode(id="not_1", type="operator", operator="~")
    constraints = Constraints(
        requested_inputs={0: QubitType(size=REGISTER_SIZE)},
        requested_input_values={},
    )

    strategy = OperatorEnricherStrategy(engine)

    results = await strategy._enrich_impl(node, constraints)

    assert len(results) == 1

    result = results[0]
    statements = result.enriched_node.implementation.statements
    gates = _only_quantum_gates(statements)

    assert result.meta_data.width == REGISTER_SIZE
    assert result.meta_data.depth == EXPECTED_DEPTH
    assert len(gates) == EXPECTED_GATE_COUNT
    assert [gate.name.name for gate in gates] == ["x", "x", "x"]


def test_dynamic_quantum_bitwise_not_requires_one_input(engine) -> None:
    node = OperatorNode(id="not_1", type="operator", operator="~")
    constraints = Constraints(
        requested_inputs={},
        requested_input_values={},
    )

    strategy = OperatorEnricherStrategy(engine)

    with pytest.raises(InputCountMismatch):
        strategy._generate_bitwise_not_enrichment(node, constraints)


def test_dynamic_quantum_bitwise_not_requires_qubit_input(engine) -> None:
    node = OperatorNode(id="not_1", type="operator", operator="~")
    constraints = Constraints(
        requested_inputs={0: object()},
        requested_input_values={},
    )

    strategy = OperatorEnricherStrategy(engine)

    with pytest.raises(InputTypeMismatch):
        strategy._generate_bitwise_not_enrichment(node, constraints)

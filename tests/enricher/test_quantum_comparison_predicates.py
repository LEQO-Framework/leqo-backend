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
SINGLE_QUBIT_SIZE = 1
INVALID_REGISTER_SIZE = 2


def _only_quantum_gates(statements: list[object]) -> list[QuantumGate]:
    return [stmt for stmt in statements if isinstance(stmt, QuantumGate)]


@pytest.mark.parametrize(
    ("operator", "expected_gates", "expected_depth"),
    [
        ("==", ["x", "cx", "cx"], 3),
        ("!=", ["cx", "cx"], 2),
        ("<", ["x", "ccx", "x"], 3),
        (">", ["x", "ccx", "x"], 3),
        ("<=", ["x", "x", "ccx", "x"], 4),
        (">=", ["x", "x", "ccx", "x"], 4),
    ],
)
@pytest.mark.asyncio
async def test_dynamic_quantum_comparison_predicates_generate_expected_gates(
    engine: AsyncEngine,
    operator: str,
    expected_gates: list[str],
    expected_depth: int,
) -> None:
    node = OperatorNode(id="cmp_1", type="operator", operator=operator)
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
    assert result.meta_data.depth == expected_depth
    assert [gate.name.name for gate in gates] == expected_gates


@pytest.mark.parametrize("operator", ["==", "!=", "<", ">", "<=", ">="])
@pytest.mark.asyncio
async def test_dynamic_quantum_comparison_predicates_require_constraints(
    engine: AsyncEngine,
    operator: str,
) -> None:
    node = OperatorNode(id="cmp_1", type="operator", operator=operator)
    strategy = OperatorEnricherStrategy(engine)

    with pytest.raises(InputCountMismatch):
        await strategy._enrich_impl(node, None)


@pytest.mark.parametrize("operator", ["==", "!=", "<", ">", "<=", ">="])
def test_dynamic_quantum_comparison_predicates_require_two_inputs(
    engine: AsyncEngine,
    operator: str,
) -> None:
    node = OperatorNode(id="cmp_1", type="operator", operator=operator)
    constraints = Constraints(
        requested_inputs={0: QubitType(size=SINGLE_QUBIT_SIZE)},
        requested_input_values={},
    )

    strategy = OperatorEnricherStrategy(engine)

    with pytest.raises(InputCountMismatch):
        strategy._generate_comparison_enrichment(node, constraints)


@pytest.mark.parametrize("operator", ["==", "!=", "<", ">", "<=", ">="])
def test_dynamic_quantum_comparison_predicates_require_qubit_inputs(
    engine: AsyncEngine,
    operator: str,
) -> None:
    node = OperatorNode(id="cmp_1", type="operator", operator=operator)
    constraints = Constraints(
        requested_inputs={
            0: QubitType(size=SINGLE_QUBIT_SIZE),
            1: FloatType(size=32),
        },
        requested_input_values={},
    )

    strategy = OperatorEnricherStrategy(engine)

    with pytest.raises(InputTypeMismatch):
        strategy._generate_comparison_enrichment(node, constraints)


@pytest.mark.parametrize("operator", ["==", "!=", "<", ">", "<=", ">="])
def test_dynamic_quantum_comparison_predicates_reject_multi_qubit_registers(
    engine: AsyncEngine,
    operator: str,
) -> None:
    node = OperatorNode(id="cmp_1", type="operator", operator=operator)
    constraints = Constraints(
        requested_inputs={
            0: QubitType(size=INVALID_REGISTER_SIZE),
            1: QubitType(size=SINGLE_QUBIT_SIZE),
        },
        requested_input_values={},
    )

    strategy = OperatorEnricherStrategy(engine)

    with pytest.raises(InputSizeMismatch):
        strategy._generate_comparison_enrichment(node, constraints)


def test_dynamic_quantum_comparison_rejects_unknown_predicate(
    engine: AsyncEngine,
) -> None:
    strategy = OperatorEnricherStrategy(engine)

    with pytest.raises(ValueError, match="Unsupported comparison operator"):
        strategy._comparison_gates(
            "===",
            strategy._qubit_reference("lhs", None),
            strategy._qubit_reference("rhs", None),
            strategy._qubit_reference("result", None),
        )

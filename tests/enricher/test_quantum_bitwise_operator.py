import pytest
from openqasm3.ast import AliasStatement, QuantumGate

from app.enricher import Constraints
from app.enricher.operator import OperatorEnricherStrategy
from app.model.CompileRequest import OperatorNode
from app.model.data_types import FloatType, QubitType
from app.model.exceptions import (
    InputCountMismatch,
    InputSizeMismatch,
    InputTypeMismatch,
)

REGISTER_SIZE = 3
EXPECTED_DEPTH = 1
EXPECTED_GATE_COUNT = 3
EXPECTED_AND_DEPTH = 1
EXPECTED_XOR_DEPTH = 2
EXPECTED_OR_DEPTH = 3
BINARY_BITWISE_REGISTER_COUNT = 3


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operator", "expected_gates", "expected_depth"),
    [
        ("&", ["ccx"] * REGISTER_SIZE, EXPECTED_AND_DEPTH),
        ("^", ["cx", "cx"] * REGISTER_SIZE, EXPECTED_XOR_DEPTH),
        ("|", ["cx", "cx", "ccx"] * REGISTER_SIZE, EXPECTED_OR_DEPTH),
    ],
)
async def test_dynamic_quantum_binary_bitwise_operators_generate_expected_gates(
    engine,
    operator: str,
    expected_gates: list[str],
    expected_depth: int,
) -> None:
    node = OperatorNode(id="bitwise-node", type="operator", operator=operator)
    constraints = Constraints(
        requested_inputs={
            0: QubitType(size=REGISTER_SIZE),
            1: QubitType(size=REGISTER_SIZE),
        },
        requested_input_values={},
    )

    strategy = OperatorEnricherStrategy(engine)

    results = await strategy._enrich_impl(node, constraints)

    assert len(results) == 1

    result = results[0]
    statements = result.enriched_node.implementation.statements
    gates = _only_quantum_gates(statements)

    assert result.meta_data.width == REGISTER_SIZE * BINARY_BITWISE_REGISTER_COUNT
    assert result.meta_data.depth == expected_depth
    assert [gate.name.name for gate in gates] == expected_gates


@pytest.mark.asyncio
@pytest.mark.parametrize("operator", ["&", "^", "|"])
async def test_dynamic_quantum_binary_bitwise_operators_require_equal_input_sizes(
    engine,
    operator: str,
) -> None:
    node = OperatorNode(id="bitwise-node", type="operator", operator=operator)
    constraints = Constraints(
        requested_inputs={
            0: QubitType(size=REGISTER_SIZE),
            1: QubitType(size=REGISTER_SIZE + 1),
        },
        requested_input_values={},
    )

    strategy = OperatorEnricherStrategy(engine)

    with pytest.raises(InputSizeMismatch):
        await strategy._enrich_impl(node, constraints)


@pytest.mark.asyncio
@pytest.mark.parametrize("operator", ["&", "^", "|"])
async def test_dynamic_quantum_binary_bitwise_operators_preserve_signed_annotation(
    engine,
    operator: str,
) -> None:
    node = OperatorNode(id="bitwise-node", type="operator", operator=operator)
    constraints = Constraints(
        requested_inputs={
            0: QubitType(size=REGISTER_SIZE, signed=True),
            1: QubitType(size=REGISTER_SIZE),
        },
        requested_input_values={},
    )

    strategy = OperatorEnricherStrategy(engine)

    results = await strategy._enrich_impl(node, constraints)

    assert len(results) == 1

    alias_statement = results[0].enriched_node.implementation.statements[-1]
    assert isinstance(alias_statement, AliasStatement)
    assert any(
        annotation.keyword == "leqo.twos_complement"
        for annotation in alias_statement.annotations
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("operator", ["&", "^", "|"])
async def test_dynamic_quantum_binary_bitwise_operators_reject_non_qubit_inputs(
    engine,
    operator: str,
) -> None:
    node = OperatorNode(id="bitwise-node", type="operator", operator=operator)
    constraints = Constraints(
        requested_inputs={
            0: QubitType(size=REGISTER_SIZE),
            1: FloatType(size=32),
        },
        requested_input_values={},
    )

    strategy = OperatorEnricherStrategy(engine)

    with pytest.raises(InputTypeMismatch):
        await strategy._enrich_impl(node, constraints)

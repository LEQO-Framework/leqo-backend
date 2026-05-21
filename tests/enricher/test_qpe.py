import pytest

from app.enricher import Constraints
from app.enricher.qpe import QPEEnricherStrategy
from app.model.CompileRequest import QPENode
from app.model.data_types import FloatType, QubitType
from app.model.exceptions import InputTypeMismatch
from app.openqasm3.printer import leqo_dumps

ESTIMATION_SIZE = 2
EXPECTED_CP_COUNT = 3


def _node() -> QPENode:
    return QPENode(
        id="qpe-node",
        label=None,
        type="qpe",
        estimationSize=ESTIMATION_SIZE,
        phase=0.25,
    )


@pytest.mark.asyncio
async def test_qpe_enrichment_contains_expected_qasm() -> None:
    constraints = Constraints(
        requested_inputs={0: QubitType(size=1)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    results = await QPEEnricherStrategy().enrich(_node(), constraints)
    result = next(iter(results))

    implementation_str = leqo_dumps(result.enriched_node.implementation)

    assert 'include "stdgates.inc";' in implementation_str
    assert "@leqo.input 0" in implementation_str
    assert "qubit[1] target;" in implementation_str
    assert "qubit[2] estimation;" in implementation_str
    assert "h estimation[0];" in implementation_str
    assert "h estimation[1];" in implementation_str
    assert implementation_str.count("cp(") == EXPECTED_CP_COUNT
    assert "swap estimation[0], estimation[1];" in implementation_str
    assert "@leqo.output 0" in implementation_str
    assert "let phase = estimation;" in implementation_str
    assert "@leqo.output 1" in implementation_str
    assert "let target_out = target;" in implementation_str
    assert result.meta_data.width == ESTIMATION_SIZE


@pytest.mark.asyncio
async def test_qpe_rejects_non_qubit_input() -> None:
    constraints = Constraints(
        requested_inputs={0: FloatType(size=32)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    with pytest.raises(InputTypeMismatch):
        await QPEEnricherStrategy().enrich(_node(), constraints)


@pytest.mark.asyncio
async def test_qpe_rejects_multi_qubit_target() -> None:
    constraints = Constraints(
        requested_inputs={0: QubitType(size=2)},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    with pytest.raises(Exception, match="single-qubit target"):
        await QPEEnricherStrategy().enrich(_node(), constraints)

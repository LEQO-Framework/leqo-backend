import pytest
from openqasm3.ast import AliasStatement

from app.enricher import Constraints
from app.enricher.qiskit_prepare import HAS_QISKIT, QiskitPrepareStateEnricherStrategy
from app.model.CompileRequest import PrepareStateNode


@pytest.mark.asyncio
async def test_qiskit_strategy_skips_when_library_missing(monkeypatch) -> None:
    monkeypatch.setattr("app.enricher.qiskit_prepare.HAS_QISKIT", False, raising=False)
    monkeypatch.setattr("app.enricher.qiskit_prepare.QuantumCircuit", None, raising=False)
    monkeypatch.setattr("app.enricher.qiskit_prepare.QuantumRegister", None, raising=False)
    monkeypatch.setattr("app.enricher.qiskit_prepare.qasm3_dumps", None, raising=False)

    strategy = QiskitPrepareStateEnricherStrategy()
    node = PrepareStateNode(
        id="test",
        label=None,
        type="prepare",
        quantumState="ghz",
        size=3,
    )
    constraints = Constraints(
        requested_inputs={},
        optimizeWidth=False,
        optimizeDepth=False,
    )

    enrichment_results = await strategy.enrich(node, constraints)

    assert enrichment_results == []


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_QISKIT, reason="Qiskit >=2 is not available")
async def test_qiskit_strategy_generates_program() -> None:
    strategy = QiskitPrepareStateEnricherStrategy()
    node = PrepareStateNode(
        id="test",
        label=None,
        type="prepare",
        quantumState="ghz",
        size=3,
    )
    constraints = Constraints(
        requested_inputs={},
        optimizeWidth=False,
        optimizeDepth=False,
    )

    enrichment_results = await strategy.enrich(node, constraints)

    assert len(enrichment_results) == 1
    result = enrichment_results[0]
    assert result.meta_data.width == node.size
    assert result.meta_data.depth is None or result.meta_data.depth > 0

    program = result.enriched_node.implementation
    assert isinstance(program.statements[-1], AliasStatement)
    annotation_names = [annotation.name for annotation in program.statements[-1].annotations]
    assert "leqo.output" in annotation_names

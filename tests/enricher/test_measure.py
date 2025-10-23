import pytest

from app.enricher import Constraints
from app.enricher.exceptions import DuplicateIndices, IndicesOutOfRange, NoIndices
from app.enricher.measure import MeasurementEnricherStrategy
from app.model.CompileRequest import MeasurementNode
from app.model.data_types import IntType, QubitType
from app.model.exceptions import InputCountMismatch, InputTypeMismatch
from tests.enricher.utils import assert_enrichment


@pytest.mark.asyncio
async def test_simple_measurement() -> None:
    node = MeasurementNode(id="nodeId", indices=[0, 1, 2])
    constraints = Constraints(
        requested_inputs={0: QubitType(3)}, optimizeWidth=False, optimizeDepth=False
    )

    strategy = MeasurementEnricherStrategy()
    result = list(await strategy.enrich(node, constraints))

    assert len(result) == 1
    assert_enrichment(
        result[0].enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        @leqo.input 0
        qubit[3] q;
        bit[3] result = measure q[{0, 1, 2}];
        @leqo.output 0
        let out = result;
        @leqo.output 1
        let qubit_out = q;
        """,
    )


@pytest.mark.asyncio
async def test_less_indices() -> None:
    node = MeasurementNode(id="nodeId", indices=[1])
    constraints = Constraints(
        requested_inputs={0: QubitType(3)}, optimizeWidth=False, optimizeDepth=False
    )

    strategy = MeasurementEnricherStrategy()
    result = list(await strategy.enrich(node, constraints))

    assert len(result) == 1
    assert_enrichment(
        result[0].enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        @leqo.input 0
        qubit[3] q;
        bit[1] result = measure q[{1}];
        @leqo.output 0
        let out = result;
        @leqo.output 1
        let qubit_out = q;
        """,
    )


@pytest.mark.asyncio
async def test_measure_single_qubit() -> None:
    node = MeasurementNode(id="nodeId", indices=[0])
    constraints = Constraints(
        requested_inputs={0: QubitType(None)}, optimizeWidth=False, optimizeDepth=False
    )

    strategy = MeasurementEnricherStrategy()
    result = list(await strategy.enrich(node, constraints))

    assert len(result) == 1
    assert_enrichment(
        result[0].enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        @leqo.input 0
        qubit q;
        bit result = measure q;
        @leqo.output 0
        let out = result;
        @leqo.output 1
        let qubit_out = q;
        """,
    )


@pytest.mark.asyncio
async def test_measure_single_qubit_with_empty_indices() -> None:
    node = MeasurementNode(id="nodeId", indices=[])
    constraints = Constraints(
        requested_inputs={0: QubitType(None)}, optimizeWidth=False, optimizeDepth=False
    )

    strategy = MeasurementEnricherStrategy()
    result = list(await strategy.enrich(node, constraints))

    assert len(result) == 1
    assert_enrichment(
        result[0].enriched_node,
        "nodeId",
        """\
        OPENQASM 3.1;
        @leqo.input 0
        qubit q;
        bit result = measure q;
        @leqo.output 0
        let out = result;
        @leqo.output 1
        let qubit_out = q;
        """,
    )


@pytest.mark.asyncio
async def test_exactly_one_input_1() -> None:
    node = MeasurementNode(id="nodeId", indices=[0])
    constraints = Constraints(
        requested_inputs={}, optimizeWidth=False, optimizeDepth=False
    )

    strategy = MeasurementEnricherStrategy()
    with pytest.raises(
        InputCountMismatch,
        match=r"^Node should have 1 inputs\. Got 0\.$",
    ):
        await strategy.enrich(node, constraints)


@pytest.mark.asyncio
async def test_exactly_one_input_2() -> None:
    node = MeasurementNode(id="nodeId", indices=[0, 5])
    constraints = Constraints(
        requested_inputs={0: QubitType(3), 1: QubitType(4)},
        optimizeWidth=False,
        optimizeDepth=False,
    )

    strategy = MeasurementEnricherStrategy()
    with pytest.raises(
        InputCountMismatch,
        match=r"^Node should have 1 inputs\. Got 2\.$",
    ):
        await strategy.enrich(node, constraints)


@pytest.mark.asyncio
async def test_qubit_type_input() -> None:
    node = MeasurementNode(id="nodeId", indices=[0])
    constraints = Constraints(
        requested_inputs={0: IntType(3)}, optimizeWidth=False, optimizeDepth=False
    )

    strategy = MeasurementEnricherStrategy()
    with pytest.raises(
        InputTypeMismatch,
        match=r"^Expected type 'qubit' for input 0\. Got 'IntType\(size=3\)'\.$",
    ):
        await strategy.enrich(node, constraints)


@pytest.mark.asyncio
async def test_at_least_one_index() -> None:
    node = MeasurementNode(id="nodeId", indices=[])
    constraints = Constraints(
        requested_inputs={0: QubitType(3)}, optimizeWidth=False, optimizeDepth=False
    )

    strategy = MeasurementEnricherStrategy()
    with pytest.raises(NoIndices, match=r"^No indices were specified$"):
        await strategy.enrich(node, constraints)


@pytest.mark.asyncio
async def test_index_out_of_range_1() -> None:
    node = MeasurementNode(id="nodeId", indices=[0, 1, 2, 3])
    constraints = Constraints(
        requested_inputs={0: QubitType(3)}, optimizeWidth=False, optimizeDepth=False
    )

    strategy = MeasurementEnricherStrategy()
    with pytest.raises(
        IndicesOutOfRange, match=r"^Indices \[3\] out of range \[0, 3\)$"
    ):
        await strategy.enrich(node, constraints)


@pytest.mark.asyncio
async def test_index_out_of_range_2() -> None:
    node = MeasurementNode(id="nodeId", indices=[1, 5, 3])
    constraints = Constraints(
        requested_inputs={0: QubitType(3)}, optimizeWidth=False, optimizeDepth=False
    )

    strategy = MeasurementEnricherStrategy()
    with pytest.raises(
        IndicesOutOfRange, match=r"^Indices \[5, 3\] out of range \[0, 3\)$"
    ):
        await strategy.enrich(node, constraints)


@pytest.mark.asyncio
async def test_duplicate_indices() -> None:
    node = MeasurementNode(id="nodeId", indices=[0, 1, 1, 2, 2])
    constraints = Constraints(
        requested_inputs={0: QubitType(3)}, optimizeWidth=False, optimizeDepth=False
    )

    strategy = MeasurementEnricherStrategy()
    with pytest.raises(DuplicateIndices, match=r"^Duplicate indices \[1, 2\]$"):
        await strategy.enrich(node, constraints)

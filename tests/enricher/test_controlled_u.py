import pytest

from app.enricher import Constraints
from app.enricher.controlled_u import (
    HAS_QISKIT_CONTROLLED_U,
    ControlledUEnricherStrategy,
)
from app.enricher.exceptions import EnricherException
from app.model.CompileRequest import ControlledUNode
from app.model.data_types import IntType, QubitType
from app.model.exceptions import (
    InputCountMismatch,
    InputSizeMismatch,
    InputTypeMismatch,
)
from app.openqasm3.printer import leqo_dumps

_CONTROLLED_U_WIDTH = 2

pytestmark = pytest.mark.skipif(
    not HAS_QISKIT_CONTROLLED_U,
    reason="Qiskit Controlled-U support is not available.",
)


def test_controlled_u_generates_qasm_with_annotations() -> None:
    node = ControlledUNode(
        id="nodeId",
        matrix=[
            [0.0, 1.0],
            [1.0, 0.0],
        ],
    )
    constraints = Constraints(
        requested_inputs={0: QubitType(1), 1: QubitType(1)},
        optimizeWidth=False,
        optimizeDepth=False,
    )

    result = list(ControlledUEnricherStrategy()._enrich_impl(node, constraints))

    assert len(result) == 1
    assert result[0].enriched_node.id == "nodeId"
    assert result[0].meta_data.width == _CONTROLLED_U_WIDTH
    assert result[0].meta_data.depth is not None

    qasm = leqo_dumps(result[0].enriched_node.implementation)

    assert "@leqo.input 0" in qasm
    assert "@leqo.input 1" in qasm
    assert "@leqo.output 0" in qasm
    assert "@leqo.output 1" in qasm
    assert "control" in qasm
    assert "target" in qasm


def test_controlled_u_control_value_zero_is_supported() -> None:
    node = ControlledUNode(
        id="nodeId",
        matrix=[
            [0.0, 1.0],
            [1.0, 0.0],
        ],
        controlValue=0,
    )
    constraints = Constraints(
        requested_inputs={0: QubitType(1), 1: QubitType(1)},
        optimizeWidth=False,
        optimizeDepth=False,
    )

    result = list(ControlledUEnricherStrategy()._enrich_impl(node, constraints))

    assert len(result) == 1
    assert result[0].meta_data.width == _CONTROLLED_U_WIDTH


def test_controlled_u_rejects_non_square_matrix() -> None:
    node = ControlledUNode(
        id="nodeId",
        matrix=[
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ],
    )

    with pytest.raises(EnricherException, match="must be square"):
        list(ControlledUEnricherStrategy()._enrich_impl(node, constraints=None))


def test_controlled_u_rejects_non_unitary_matrix() -> None:
    node = ControlledUNode(
        id="nodeId",
        matrix=[
            [1.0, 1.0],
            [0.0, 1.0],
        ],
    )

    with pytest.raises(EnricherException, match="must be unitary"):
        list(ControlledUEnricherStrategy()._enrich_impl(node, constraints=None))


def test_controlled_u_requires_two_inputs() -> None:
    node = ControlledUNode(
        id="nodeId",
        matrix=[
            [1.0, 0.0],
            [0.0, 1.0],
        ],
    )
    constraints = Constraints(
        requested_inputs={0: QubitType(1)},
        optimizeWidth=False,
        optimizeDepth=False,
    )

    with pytest.raises(InputCountMismatch):
        list(ControlledUEnricherStrategy()._enrich_impl(node, constraints))


def test_controlled_u_requires_qubit_inputs() -> None:
    node = ControlledUNode(
        id="nodeId",
        matrix=[
            [1.0, 0.0],
            [0.0, 1.0],
        ],
    )
    constraints = Constraints(
        requested_inputs={0: IntType(1), 1: QubitType(1)},
        optimizeWidth=False,
        optimizeDepth=False,
    )

    with pytest.raises(InputTypeMismatch):
        list(ControlledUEnricherStrategy()._enrich_impl(node, constraints))


def test_controlled_u_requires_single_control_qubit() -> None:
    node = ControlledUNode(
        id="nodeId",
        matrix=[
            [1.0, 0.0],
            [0.0, 1.0],
        ],
    )
    constraints = Constraints(
        requested_inputs={0: QubitType(2), 1: QubitType(1)},
        optimizeWidth=False,
        optimizeDepth=False,
    )

    with pytest.raises(InputSizeMismatch):
        list(ControlledUEnricherStrategy()._enrich_impl(node, constraints))


def test_controlled_u_target_size_must_match_matrix_dimension() -> None:
    node = ControlledUNode(
        id="nodeId",
        matrix=[
            [1.0, 0.0],
            [0.0, 1.0],
        ],
    )
    constraints = Constraints(
        requested_inputs={0: QubitType(1), 1: QubitType(2)},
        optimizeWidth=False,
        optimizeDepth=False,
    )

    with pytest.raises(InputSizeMismatch):
        list(ControlledUEnricherStrategy()._enrich_impl(node, constraints))

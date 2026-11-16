import pytest
from pydantic import ValidationError

from app.model.CompileRequest import CompileRequest, QubitNode

REGISTER_SIZE = 2


def _metadata() -> dict:
    return {
        "version": "1.0.0",
        "name": "test",
        "description": "",
        "author": "",
    }


def test_qubit_node_defaults_to_size_1() -> None:
    node = QubitNode(id="q1", type="qubit")

    assert node.size == 1


def test_qubit_node_accepts_register_size() -> None:
    node = QubitNode(id="q1", type="qubit", size=REGISTER_SIZE)

    assert node.size == REGISTER_SIZE


def test_qubit_node_rejects_zero_size() -> None:
    with pytest.raises(ValidationError):
        QubitNode(id="q1", type="qubit", size=0)


def test_data_type_node_qubit_is_normalized_to_qubit_node() -> None:
    request = CompileRequest.model_validate(
        {
            "metadata": _metadata(),
            "nodes": [
                {
                    "id": "q1",
                    "type": "dataTypeNode",
                    "data": {
                        "dataType": "qubit",
                        "size": REGISTER_SIZE,
                    },
                }
            ],
            "edges": [],
        }
    )

    node = request.nodes[0]

    assert isinstance(node, QubitNode)
    assert node.type == "qubit"
    assert node.size == REGISTER_SIZE

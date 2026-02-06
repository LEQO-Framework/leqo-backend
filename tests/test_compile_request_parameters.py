import pytest
from pydantic import ValidationError

from app.model.CompileRequest import CompileRequest


def _base_request(nodes: list[dict], *, parameters: dict | None = None) -> dict:
    payload = {
        "metadata": {
            "version": "1.0.0",
            "name": "Param model",
            "description": "Test parameters",
            "author": "",
        },
        "nodes": nodes,
        "edges": [],
    }
    if parameters is not None:
        payload["parameters"] = parameters
    return payload


def test_compile_request_resolves_parameters() -> None:
    payload = _base_request(
        [
            {"id": "q0", "type": "qubit", "size": "$n"},
            {
                "id": "g0",
                "type": "gate-with-param",
                "gate": "rx",
                "parameter": "$theta",
            },
            {"id": "lit", "type": "int", "value": "$k", "bitSize": "$bits"},
            {
                "id": "arr",
                "type": "array",
                "values": "$vals",
                "elementBitSize": "$elem_bits",
            },
            {"id": "m", "type": "measure", "indices": "$idxs"},
        ],
        parameters={
            "n": 2,
            "theta": 0.5,
            "k": 3,
            "bits": 5,
            "vals": [1, 2, 3],
            "elem_bits": 4,
            "idxs": [0, 1],
        },
    )

    request = CompileRequest.model_validate(payload)
    nodes_by_id = {node.id: node for node in request.nodes}

    assert nodes_by_id["q0"].size == 2
    assert nodes_by_id["g0"].parameter == 0.5
    assert nodes_by_id["lit"].value == 3
    assert nodes_by_id["lit"].bitSize == 5
    assert nodes_by_id["arr"].values == [1, 2, 3]
    assert nodes_by_id["arr"].elementBitSize == 4
    assert nodes_by_id["m"].indices == [0, 1]


def test_compile_request_missing_parameter_raises() -> None:
    payload = _base_request(
        [{"id": "q0", "type": "qubit", "size": "$n"}],
        parameters={},
    )

    with pytest.raises(ValidationError) as exc:
        CompileRequest.model_validate(payload)

    assert "Unknown parameter 'n'" in str(exc.value)


def test_compile_request_rejects_invalid_parameter_value() -> None:
    payload = _base_request(
        [{"id": "b0", "type": "bit", "value": "$b"}],
        parameters={"b": 2},
    )

    with pytest.raises(ValidationError):
        CompileRequest.model_validate(payload)

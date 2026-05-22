from app.model.CompileRequest import CompileRequest, EncodeValueNode

STATE_VECTOR = "1,0,0,0"


def _metadata() -> dict:
    return {
        "version": "1.0.0",
        "name": "test",
        "description": "",
        "author": "",
    }


def test_schmidt_state_preparation_payload_is_normalized_to_encode() -> None:
    request = CompileRequest.model_validate(
        {
            "metadata": _metadata(),
            "nodes": [
                {
                    "id": "array_1",
                    "type": "dataTypeNode",
                    "data": {
                        "label": "Array",
                        "dataType": "Array",
                        "value": STATE_VECTOR,
                    },
                },
                {
                    "id": "schmidt_1",
                    "type": "statePreparationNode",
                    "data": {
                        "label": "Schmidt Decomposition",
                        "encodingType": "Schmidt Decomposition",
                    },
                },
            ],
            "edges": [
                {
                    "source": "array_1",
                    "sourceHandle": "classicalHandleDataTypeOutput0array_1",
                    "target": "schmidt_1",
                    "targetHandle": "classicalHandleStatePreparationInput0schmidt_1",
                    "type": "classicalEdge",
                }
            ],
        }
    )

    node = request.nodes[1]

    assert isinstance(node, EncodeValueNode)
    assert node.type == "encode"
    assert node.encoding == "schmidt"
    assert request.edges[0].source == ("array_1", 0)
    assert request.edges[0].target == ("schmidt_1", 0)

import asyncio
import xml.etree.ElementTree as ET
from typing import Any

from app.enricher import Enricher
from app.model.CompileRequest import ApiConnectorNode, CompileRequest
from app.transformation_manager import MergingProcessor, WorkflowProcessor
from app.transformation_manager.api_connector import (
    add_http_connector,
    api_connector_task_id,
)
from app.transformation_manager.frontend_graph import FrontendGraph

BPMN = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"
CAMUNDA_NS = "http://camunda.org/schema/1.0/bpmn"
CAMUNDA = f"{{{CAMUNDA_NS}}}"

QASM_CODE = """OPENQASM 3.1;
include "stdgates.inc";
qubit[1] q;
h q[0];
@leqo.output 0
let out = q;
"""

PAYLOAD = 'def request = [:];\nrequest.put("circuit", execution.getVariable("circuit"));\nreturn new groovy.json.JsonBuilder(request).toString();'
COUNTS = 'def resp = new groovy.json.JsonSlurperClassic().parseText(connector.getVariable("response"));\nreturn resp?.get("counts");'


def _api_node(**changes: Any) -> dict[str, Any]:
    return {
        "id": "api",
        "type": "api-connector",
        "label": "Execute Circuit",
        "method": "POST",
        "url": "/execution-service",
        "headers": {"Accept": "application/json", "Content-Type": "application/json"},
        "payload": PAYLOAD,
        "outputs": [{"name": "counts", "script": COUNTS}],
        **changes,
    }


def _request(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> CompileRequest:
    return CompileRequest.model_validate(
        {
            "metadata": {
                "version": "1.0.0",
                "name": "api",
                "description": "",
                "author": "",
            },
            "compilation_target": "workflow",
            "nodes": nodes,
            "edges": edges,
        }
    )


def _connector(node: dict[str, Any]) -> ET.Element:
    ext = ET.Element("extensionElements")
    return add_http_connector(ext, ApiConnectorNode.model_validate(node), CAMUNDA_NS)


def test_http_connector_parameters() -> None:
    connector = _connector(_api_node())
    assert connector.findtext(f"{CAMUNDA}connectorId") == "http-connector"

    io = connector.find(f"{CAMUNDA}inputOutput")
    assert io is not None
    inputs = {p.get("name"): p for p in io.findall(f"{CAMUNDA}inputParameter")}
    assert list(inputs) == ["method", "headers", "url", "payload"]
    assert inputs["method"].text == "POST"
    assert inputs["url"].text == "/execution-service"
    entries = {e.get("key"): e.text for e in inputs["headers"].iter(f"{CAMUNDA}entry")}
    assert entries == {"Accept": "application/json", "Content-Type": "application/json"}
    script = inputs["payload"].find(f"{CAMUNDA}script")
    assert script is not None
    assert script.get("scriptFormat") == "groovy"
    assert script.text == PAYLOAD

    outputs = io.findall(f"{CAMUNDA}outputParameter")
    assert [o.get("name") for o in outputs] == ["counts"]
    assert outputs[0].findtext(f"{CAMUNDA}script") == COUNTS


def test_get_request_has_no_payload_and_no_empty_headers() -> None:
    connector = _connector(_api_node(method="GET", headers={}))
    names = [p.get("name") for p in connector.iter(f"{CAMUNDA}inputParameter")]
    assert names == ["method", "url"]


def test_api_connector_is_not_compiled_to_qasm() -> None:
    request = _request(
        [
            {"id": "q", "type": "implementation", "implementation": QASM_CODE},
            _api_node(),
        ],
        [{"source": ["q", 0], "target": ["api", 0]}],
    )
    graph = FrontendGraph.create(request.nodes, request.edges)
    processor = MergingProcessor(Enricher(), graph, request.metadata)

    qasm_processor = processor.without_service_nodes()
    assert qasm_processor is not None
    assert set(qasm_processor.frontend_graph.nodes) == {"q"}
    assert "/* Start node q */" in asyncio.run(qasm_processor.process())


def test_workflow_contains_one_service_task_per_api_connector() -> None:
    request = _request(
        [
            {"id": "q", "type": "implementation", "implementation": QASM_CODE},
            _api_node(),
            _api_node(id="api2", label="Post Processing"),
        ],
        [
            {"source": ["q", 0], "target": ["api", 0]},
            {"source": ["api", 0], "target": ["api2", 0]},
        ],
    )
    graph = FrontendGraph.create(request.nodes, request.edges)
    processor = WorkflowProcessor(
        Enricher(),
        graph,
        request.metadata,
        result="OPENQASM 3.1;",
        original_request=request,
    )

    root = ET.fromstring(asyncio.run(processor.process()))
    for node_id, label in [("api", "Execute Circuit"), ("api2", "Post Processing")]:
        task = root.find(
            f".//{BPMN}serviceTask[@id='{api_connector_task_id(node_id)}']"
        )
        assert task is not None
        assert task.get("name") == label
        assert task.find(f".//{CAMUNDA}connector") is not None

    flows = [
        (flow.get("sourceRef"), flow.get("targetRef"))
        for flow in root.iter(f"{BPMN}sequenceFlow")
    ]
    assert ("Task_quantum_group_0_human", api_connector_task_id("api")) in flows
    assert (api_connector_task_id("api"), api_connector_task_id("api2")) in flows
    assert (api_connector_task_id("api2"), "EndEvent_1") in flows

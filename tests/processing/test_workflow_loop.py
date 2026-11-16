import asyncio
import xml.etree.ElementTree as ET
from typing import Any

import pytest
from pydantic import ValidationError

from app.enricher import Enricher
from app.model.CompileRequest import CompileRequest, RepeatNode
from app.transformation_manager import MergingProcessor, WorkflowProcessor
from app.transformation_manager.frontend_graph import FrontendGraph
from app.transformation_manager.python_service import (
    parse_python_implementation,
    python_service_task_id,
)
from app.transformation_manager.workflow_loop import (
    condition_variables,
    loop_counter_variable,
    loop_gateway_id,
)

BPMN = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"
CAMUNDA = "{http://camunda.org/schema/1.0/bpmn}"


def _repeat(loop: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "loop",
        "type": "repeat",
        **loop,
        "block": {
            "nodes": [
                {
                    "id": "inc",
                    "type": "implementation",
                    "language": "python",
                    "implementation": "# @input a\n# @output b\nb = a + 1\n",
                },
                {
                    "id": "dec",
                    "type": "implementation",
                    "language": "python",
                    "implementation": "@input a\n@output a\n\na = a - 1\n",
                },
            ],
            "edges": [
                {"source": ["dec", 0], "target": ["loop", 0]},
                {"source": ["inc", 0], "target": ["dec", 0]},
                {"source": ["loop", 0], "target": ["inc", 0]},
            ],
        },
    }


def _workflow(loop: dict[str, Any]) -> ET.Element:
    request = CompileRequest.model_validate(
        {
            "metadata": {
                "version": "1.0.0",
                "name": "loop",
                "description": "",
                "author": "",
            },
            "compilation_target": "workflow",
            "nodes": [_repeat(loop), {"id": "lit", "type": "int", "value": 1}],
            "edges": [
                {"source": ["lit", 0], "target": ["loop", 0], "identifier": "a"}
            ],
        }
    )
    graph = FrontendGraph.create(request.nodes, request.edges)
    processor = MergingProcessor(Enricher(), graph, request.metadata)
    # the loop is a service node, nothing is compiled into OpenQASM
    assert processor.without_service_nodes() is None

    workflow = WorkflowProcessor(
        Enricher(), graph, request.metadata, result="", original_request=request
    )
    bpmn = asyncio.run(workflow.process())
    assert bpmn, "BPMN generation failed"
    assert workflow.service_deployment_models is not None
    return ET.fromstring(bpmn)


def _flows(root: ET.Element) -> dict[tuple[str, str], ET.Element]:
    return {
        (flow.get("sourceRef"), flow.get("targetRef")): flow
        for flow in root.iter(f"{BPMN}sequenceFlow")
    }


def _listeners(flow: ET.Element) -> list[str | None]:
    return [
        listener.get("expression")
        for listener in flow.iter(f"{CAMUNDA}executionListener")
    ]


def test_loop_with_condition() -> None:
    root = _workflow({"condition": "a>=1"})
    gateway_id = loop_gateway_id("loop")
    inc, dec = python_service_task_id("inc"), python_service_task_id("dec")
    flows = _flows(root)

    gateway = root.find(f".//{BPMN}exclusiveGateway[@id='{gateway_id}']")
    assert gateway is not None

    # gateway -> body -> back to the gateway
    entry = flows[(gateway_id, inc)]
    condition = entry.find(f"{BPMN}conditionExpression")
    assert condition is not None
    assert condition.text == "${a>=1}"
    assert (inc, dec) in flows
    assert _listeners(flows[(dec, gateway_id)]) == []

    # the literal is written by the first service task, before the loop
    literal_task = root.find(f".//{BPMN}serviceTask[@id='Task_lit']")
    assert literal_task is not None
    assert literal_task.get(f"{CAMUNDA}expression") == (
        "${execution.setVariable('a', 1)}"
    )
    assert ("StartEvent_1", "Task_lit") in flows
    assert _listeners(flows[("Task_lit", gateway_id)]) == []

    # leaving the loop is the default flow
    exit_flow = flows[(gateway_id, "Task_analyze_results")]
    assert gateway.get("default") == exit_flow.get("id")
    assert ("Task_analyze_results", "EndEvent_1") in flows

    # a is set in the workflow, so it is not asked in the start form
    start_event = root.find(f".//{BPMN}startEvent")
    assert start_event is not None
    assert "a" not in {f.get("id") for f in start_event.iter(f"{CAMUNDA}formField")}


def test_loop_with_iterations_counts() -> None:
    root = _workflow({"iterations": 3})
    gateway_id = loop_gateway_id("loop")
    counter = loop_counter_variable("loop")
    inc, dec = python_service_task_id("inc"), python_service_task_id("dec")
    flows = _flows(root)

    condition = flows[(gateway_id, inc)].find(f"{BPMN}conditionExpression")
    assert condition is not None
    assert condition.text == "${" + counter + " < 3}"
    assert _listeners(flows[("Task_lit", gateway_id)]) == [
        f"${{execution.setVariable('{counter}', 0)}}"
    ]
    assert _listeners(flows[(dec, gateway_id)]) == [
        f"${{execution.setVariable('{counter}', {counter} + 1)}}"
    ]


def test_condition_variable_missing_in_model_is_asked() -> None:
    loop = _repeat({"condition": "threshold > 0"})
    root_request = CompileRequest.model_validate(
        {
            "metadata": {"version": "1.0.0", "name": "loop", "description": "", "author": ""},
            "compilation_target": "workflow",
            "nodes": [loop],
            "edges": [],
        }
    )
    graph = FrontendGraph.create(root_request.nodes, root_request.edges)
    workflow = WorkflowProcessor(
        Enricher(), graph, root_request.metadata, result="", original_request=root_request
    )
    root = ET.fromstring(asyncio.run(workflow.process()))
    start_event = root.find(f".//{BPMN}startEvent")
    assert start_event is not None
    fields = {f.get("id") for f in start_event.iter(f"{CAMUNDA}formField")}
    # threshold is not set anywhere; without the literal, a is only set by dec,
    # which runs after inc read it in the first iteration
    assert "threshold" in fields
    assert "a" in fields


def test_repeat_needs_iterations_or_condition() -> None:
    with pytest.raises(ValidationError, match="iterations or a condition"):
        RepeatNode.model_validate(
            {"id": "loop", "type": "repeat", "block": {"nodes": [], "edges": []}}
        )


def test_condition_variables() -> None:
    node = RepeatNode.model_validate(
        {
            "id": "loop",
            "type": "repeat",
            "condition": "a >= 1e3 and not done or name == 'x y'",
            "block": {"nodes": [], "edges": []},
        }
    )
    assert condition_variables(node) == ["a", "done", "name"]


def test_annotations_without_hash() -> None:
    parsed = parse_python_implementation("@input a\n@output a\n\na = a - 1\n")
    assert parsed.interface.inputs == ["a"]
    assert parsed.interface.outputs == ["a"]

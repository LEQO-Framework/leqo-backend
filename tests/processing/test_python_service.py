import asyncio
import importlib.util
import io
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

import pytest

from app.enricher import Enricher
from app.enricher.exceptions import PythonImplementationNotSupported
from app.model.CompileRequest import CompileRequest, ImplementationNode
from app.transformation_manager import MergingProcessor, WorkflowProcessor
from app.transformation_manager.frontend_graph import FrontendGraph
from app.transformation_manager.python_service import (
    INPUTS_VARIABLE,
    PythonAnnotationError,
    detect_requirements,
    generate_service_code,
    generate_service_deployment_models,
    parse_python_implementation,
    python_service_deployment_model_url,
    python_service_task_id,
    python_service_topic,
)

BPMN = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"
CAMUNDA = "{http://camunda.org/schema/1.0/bpmn}"
OPENTOSCA = "{https://github.com/UST-QuAntiL/OpenTOSCA}"

PYTHON_CODE = """import numpy as np

# @input data
# @output result, count

# @input
factor = 2

values = [float(x) * factor for x in data.split(",")]
result = values  # @output
count = len(values)
"""

QASM_CODE = """OPENQASM 3.1;
include "stdgates.inc";
qubit[1] q;
h q[0];
@leqo.output 0
let out = q;
"""


def _run(code: str, inputs: dict[str, Any]) -> dict[str, Any]:
    namespace: dict[str, Any] = {INPUTS_VARIABLE: inputs, **inputs}
    exec(compile(code, "user_code.py", "exec"), namespace)
    return namespace


def _request(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]], target: str
) -> CompileRequest:
    return CompileRequest.model_validate(
        {
            "metadata": {
                "version": "1.0.0",
                "name": "python",
                "description": "",
                "author": "",
            },
            "compilation_target": target,
            "nodes": nodes,
            "edges": edges,
        }
    )


def test_parse_annotations() -> None:
    parsed = parse_python_implementation(PYTHON_CODE)

    assert parsed.interface.inputs == ["data", "factor"]
    assert parsed.interface.required_inputs == ["data"]
    assert parsed.interface.outputs == ["result", "count"]
    assert f"factor = {INPUTS_VARIABLE}.get('factor', 2)" in parsed.code
    # comments of the user code are kept
    assert "result = values  # @output" in parsed.code


def test_rewritten_defaults() -> None:
    code = "# @input\nx: int = 1 + 1\n# @output y\ny = x * 10\n"
    parsed = parse_python_implementation(code)

    assert _run(parsed.code, {})["y"] == 2 * 10
    assert _run(parsed.code, {"x": 5})["y"] == 5 * 10


def test_input_without_value() -> None:
    parsed = parse_python_implementation("# @input\nx: int\ny = x  # @output\n")

    assert parsed.interface.required_inputs == ["x"]
    assert parsed.interface.outputs == ["y"]


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("# @input\nprint(1)\n", "must be attached"),
        ("# @output\n", "must be attached"),
        ("# @input 1abc\n", "not a valid variable name"),
        ("def f(:\n", "not valid python code"),
    ],
)
def test_invalid_annotations(code: str, message: str) -> None:
    with pytest.raises(PythonAnnotationError, match=message):
        parse_python_implementation(code)


def test_unrelated_comments_are_ignored() -> None:
    parsed = parse_python_implementation("# @inputs are read below\nx = '# @input'\n")

    assert parsed.interface.inputs == []


def test_detect_requirements() -> None:
    code = "import os\nimport numpy as np\nfrom sklearn.cluster import KMeans\nfrom . import x\n"

    assert detect_requirements(code) == ["numpy", "requests", "scikit-learn"]


def test_qasm_target_rejects_python() -> None:
    node = ImplementationNode(id="py", implementation="x = 1", language="python")

    with pytest.raises(PythonImplementationNotSupported):
        asyncio.run(Enricher().enrich(node, None))


def test_service_zip_layout() -> None:
    node = ImplementationNode(id="py", implementation=PYTHON_CODE, language="python")
    content = generate_service_deployment_models([node])
    assert content is not None

    with zipfile.ZipFile(io.BytesIO(content)) as master:
        assert master.namelist() == [f"{python_service_task_id('py')}.zip"]
        service = zipfile.ZipFile(io.BytesIO(master.read(master.namelist()[0])))

    assert sorted(service.namelist()) == ["Dockerfile", "service.zip"]
    dockerfile = service.read("Dockerfile").decode()
    assert f"ENV CAMUNDA_TOPIC={python_service_topic('py')}" in dockerfile

    inner = zipfile.ZipFile(io.BytesIO(service.read("service.zip")))
    assert sorted(inner.namelist()) == ["requirements.txt", "service.py"]
    assert inner.read("requirements.txt").decode().split() == ["numpy", "requests"]

    service_code = inner.read("service.py").decode()
    assert f"    data = {INPUTS_VARIABLE}['data']\n" in service_code
    assert f"    factor = {INPUTS_VARIABLE}.get('factor', 2)\n" in service_code
    assert "    result = values  # @output\n" in service_code


def _service_code(code: str) -> str:
    return generate_service_code(
        "py", python_service_topic("py"), parse_python_implementation(code)
    )


def test_embedded_code_keeps_multiline_strings() -> None:
    code = 'def a():\r\n    return """x\r\ny"""\r\n\r\nresult = a()  # @output\r\n'
    namespace: dict[str, Any] = {"__name__": "service"}
    exec(_service_code(code).split("def read_variable")[0], namespace)

    assert namespace["run_user_code"]({}) == {"result": "x\ny"}


def test_code_that_cannot_be_embedded() -> None:
    with pytest.raises(PythonAnnotationError, match="cannot be embedded"):
        _service_code("from os import *\nresult = 1  # @output\n")


def test_no_python_nodes() -> None:
    node = ImplementationNode(id="q", implementation=QASM_CODE)

    assert generate_service_deployment_models([node]) is None


def test_generated_service_handles_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    code = "# @input data\n# @input\nfactor = 2\n# @output\nresult = [int(x) * factor for x in data.split(',')]\n"
    node = ImplementationNode(id="py", implementation=code, language="python")
    content = generate_service_deployment_models([node])
    assert content is not None
    with zipfile.ZipFile(io.BytesIO(content)) as master:
        service = zipfile.ZipFile(io.BytesIO(master.read(master.namelist()[0])))
    zipfile.ZipFile(io.BytesIO(service.read("service.zip"))).extractall(tmp_path)

    monkeypatch.setenv("CAMUNDA_ENDPOINT", "http://camunda/engine-rest")
    spec = importlib.util.spec_from_file_location(
        "generated_service", tmp_path / "service.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    posted: list[tuple[str, Any]] = []

    class Response:
        status_code = 204

    def post(url: str, json: Any) -> Response:
        posted.append((url, json))
        return Response()

    monkeypatch.setattr(module.requests, "post", post)

    module.handle_task(
        {
            "id": "task1",
            "processInstanceId": "p1",
            "variables": {
                "data": {"type": "String", "value": "1,2,3"},
                "factor": {"type": "Long", "value": 10},
            },
        }
    )
    assert posted == [
        (
            "http://camunda/engine-rest/external-task/task1/complete",
            {
                "workerId": module.WORKER_ID,
                "variables": {"result": {"value": "[10, 20, 30]", "type": "String"}},
            },
        )
    ]

    with pytest.raises(RuntimeError, match="Missing input variables: data"):
        module.handle_task({"id": "task2", "processInstanceId": "p1", "variables": {}})


def test_without_service_nodes() -> None:
    request = _request(
        [
            {"id": "q", "type": "implementation", "implementation": QASM_CODE},
            {
                "id": "py",
                "type": "implementation",
                "language": "python",
                "implementation": "# @input x\ny = x  # @output\n",
            },
        ],
        [{"source": ["q", 0], "target": ["py", 0]}],
        "workflow",
    )
    graph = FrontendGraph.create(request.nodes, request.edges)
    processor = MergingProcessor(Enricher(), graph, request.metadata)

    filtered = processor.without_service_nodes()
    assert filtered is not None
    assert set(filtered.frontend_graph.nodes) == {"q"}
    assert "/* Start node q */" in asyncio.run(filtered.process())

    only_python = MergingProcessor(
        Enricher(),
        FrontendGraph.create([request.nodes[1]], []),
        request.metadata,
    )
    assert only_python.without_service_nodes() is None


def test_without_python_nodes_python_feeds_quantum() -> None:
    request = _request(
        [
            {"id": "lit", "type": "int", "value": 2},
            {
                "id": "py",
                "type": "implementation",
                "language": "python",
                "implementation": "# @input n\nresult = n  # @output\n",
            },
            {"id": "enc", "type": "encode", "encoding": "basis", "bounds": 0},
            {"id": "m", "type": "measure", "indices": []},
        ],
        [
            {"source": ["lit", 0], "target": ["py", 0]},
            {"source": ["py", 0], "target": ["enc", 0]},
            {"source": ["enc", 0], "target": ["m", 0]},
        ],
        "workflow",
    )
    graph = FrontendGraph.create(request.nodes, request.edges)
    processor = MergingProcessor(Enricher(), graph, request.metadata)

    # the input of the encode node is only known at runtime
    assert processor.without_service_nodes() is None


def test_workflow_contains_service_task() -> None:
    python_code = "# @input threshold, data\n# @output\nresult = data\n"
    request = _request(
        [
            {"id": "q", "type": "implementation", "implementation": QASM_CODE},
            {"id": "lit", "type": "int", "value": 7},
            {
                "id": "py",
                "type": "implementation",
                "language": "python",
                "label": "Post Processing",
                "implementation": python_code,
            },
        ],
        [
            {"source": ["q", 0], "target": ["py", 1]},
            {"source": ["lit", 0], "target": ["py", 0]},
        ],
        "workflow",
    )
    graph = FrontendGraph.create(request.nodes, request.edges)
    processor = WorkflowProcessor(
        Enricher(),
        graph,
        request.metadata,
        result="OPENQASM 3.1;",
        original_request=request,
    )

    bpmn = asyncio.run(processor.process())
    assert processor.service_deployment_models is not None

    root = ET.fromstring(bpmn)
    task = root.find(f".//{BPMN}serviceTask[@id='{python_service_task_id('py')}']")
    assert task is not None
    assert task.get("name") == "Post Processing"
    assert task.get(f"{CAMUNDA}type") == "external"
    assert task.get(f"{CAMUNDA}topic") == python_service_topic("py")
    assert task.get(f"{OPENTOSCA}deploymentModelUrl") == (
        "{{ wineryEndpoint }}/servicetemplates/"
        "http%253A%252F%252Fquantil.org%252Fquantme%252Fpull/"
        f"{python_service_task_id('py')}/?csar"
    )
    assert task.get(
        f"{OPENTOSCA}deploymentModelUrl"
    ) == python_service_deployment_model_url("py")

    # input 0 is connected to the literal (without identifier, so its variable is
    # named after its task), input 1 is missing in the model
    literal_task = root.find(f".//{BPMN}serviceTask[@id='Task_lit']")
    assert literal_task is not None
    assert literal_task.get(f"{CAMUNDA}expression") == (
        "${execution.setVariable('Task_lit_variable', 7)}"
    )
    params = {
        param.get("name"): param.text
        for param in task.iter(f"{CAMUNDA}inputParameter")
    }
    assert params == {"threshold": "${execution.getVariable('Task_lit_variable')}"}
    fields = {field.get("id"): field for field in root.iter(f"{CAMUNDA}formField")}
    assert "threshold" not in fields
    assert fields["data"].get("defaultValue") == ""

    # the quantum chain is connected to the python task
    flows = [
        (flow.get("sourceRef"), flow.get("targetRef"))
        for flow in root.iter(f"{BPMN}sequenceFlow")
    ]
    assert ("Task_quantum_group_0_human", python_service_task_id("py")) in flows
    assert (python_service_task_id("py"), "Task_analyze_results") in flows
    assert ("Task_analyze_results", "EndEvent_1") in flows

    # the user task before the end event shows the outputs
    user_task = root.find(f".//{BPMN}userTask[@id='Task_analyze_results']")
    assert user_task is not None
    fields = user_task.iter(f"{CAMUNDA}formField")
    assert [field.get("id") for field in fields] == ["result"]


def test_workflow_python_inputs_matched_by_identifier() -> None:
    python_code = "# @input factor\n# @input a\n# @output result\nresult = factor * a\n"
    request = _request(
        [
            {"id": "lit", "type": "int", "value": 2},
            {
                "id": "py",
                "type": "implementation",
                "language": "python",
                "implementation": python_code,
            },
        ],
        # the edge targets input 0 (factor), but its identifier names the variable a
        [{"source": ["lit", 0], "target": ["py", 0], "identifier": "a"}],
        "workflow",
    )
    graph = FrontendGraph.create(request.nodes, request.edges)
    processor = WorkflowProcessor(
        Enricher(),
        graph,
        request.metadata,
        result="",
        original_request=request,
    )

    root = ET.fromstring(asyncio.run(processor.process()))
    task = root.find(f".//{BPMN}serviceTask[@id='{python_service_task_id('py')}']")
    assert task is not None
    # the literal task writes a, which the python service reads directly
    literal_task = root.find(f".//{BPMN}serviceTask[@id='Task_lit']")
    assert literal_task is not None
    assert literal_task.get(f"{CAMUNDA}expression") == (
        "${execution.setVariable('a', 2)}"
    )
    assert list(task.iter(f"{CAMUNDA}inputParameter")) == []

    # only the input missing in the model is asked in the start form
    start_event = root.find(f".//{BPMN}startEvent")
    assert start_event is not None
    fields = {field.get("id") for field in start_event.iter(f"{CAMUNDA}formField")}
    assert "factor" in fields
    assert "a" not in fields

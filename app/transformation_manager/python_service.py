"""
Support for :class:`~app.model.CompileRequest.ImplementationNode` with ``language == "python"``.

Python implementations cannot be compiled into OpenQASM.
For the workflow target they become Camunda external service tasks, backed by a
generated polling service that is packaged as a deployment model (ZIP).

The interface of the service is declared with comment annotations in the python code::

    # @input data, centroids        <- declares inputs, must be provided by the workflow
    # @output result                <- declares outputs, written back as process variables

    # @input
    max_qubits = 5                  <- input with default value (used if variable is missing)

    circuits = compute(data)  # @output

Inputs are read from the process variables of the external task,
outputs are sent back as process variables when the task is completed.
"""

from __future__ import annotations

import ast
import io
import json
import re
import sys
import tokenize
import zipfile
from urllib.parse import quote
from dataclasses import dataclass, field
from typing import Any

from app.model.CompileRequest import ImplementationNode

QUANTME_NAMESPACE_PULL = "http://quantil.org/quantme/pull"
"""Namespace of the ServiceTemplates of services bound with the pulling pattern."""

INPUTS_VARIABLE = "__leqo_inputs__"
"""Name of the dict injected into the user code that holds the fetched input variables."""

_ANNOTATION_REGEX = re.compile(r"^#\s*@(input|output)\b(.*)$")
_BARE_ANNOTATION_REGEX = re.compile(r"^([ \t]*)(@(?:input|output)\b)", re.MULTILINE)


def normalize_annotations(code: str) -> str:
    """
    Turn annotations written without ``#`` (``@input a`` at line start) into comments.
    """
    return _BARE_ANNOTATION_REGEX.sub(r"\1# \2", code)
_IDENTIFIER_SEPARATOR_REGEX = re.compile(r"[\s,]+")

_PACKAGE_ALIASES = {
    "sklearn": "scikit-learn",
    "cv2": "opencv-python",
    "yaml": "pyyaml",
    "PIL": "pillow",
    "bs4": "beautifulsoup4",
    "dateutil": "python-dateutil",
}


class PythonAnnotationError(ValueError):
    """
    Raised if the annotations of a python implementation are invalid.
    """


@dataclass
class PythonServiceInterface:
    """
    Interface of a python implementation parsed from its annotations.
    """

    inputs: list[str] = field(default_factory=list)
    """All input variables in order of appearance."""

    required_inputs: list[str] = field(default_factory=list)
    """Inputs without default value."""

    outputs: list[str] = field(default_factory=list)
    """All output variables in order of appearance."""


@dataclass
class ParsedPythonImplementation:
    """
    Python implementation with parsed interface and rewritten code.
    """

    interface: PythonServiceInterface
    code: str
    """User code where annotated input assignments read from :data:`INPUTS_VARIABLE`."""


def is_python_implementation(node: object) -> bool:
    """
    Check whether the node is an :class:`~app.model.CompileRequest.ImplementationNode` in python.
    """
    return isinstance(node, ImplementationNode) and node.language == "python"


def python_service_task_id(node_id: str) -> str:
    """
    ID of the BPMN service task created for a python node.
    """
    return f"Task_{node_id}_python_service"


def python_service_topic(node_id: str) -> str:
    """
    Camunda external task topic of the service created for a python node.
    """
    return "leqo_python_" + re.sub(r"[^A-Za-z0-9_-]", "_", node_id)


def python_service_deployment_model_url(node_id: str) -> str:
    """
    URL of the deployment model (ServiceTemplate in the Winery) of the service created for a python node.

    The Winery endpoint is a placeholder that is resolved by the frontend before deployment.
    """
    namespace = quote(quote(QUANTME_NAMESPACE_PULL, safe=""), safe="")
    return (
        "{{ wineryEndpoint }}/servicetemplates/"
        f"{namespace}/{python_service_task_id(node_id)}/?csar"
    )


def _add_unique(target: list[str], name: str) -> None:
    if name not in target:
        target.append(name)


def _assignment_target(statement: ast.stmt) -> tuple[str, ast.expr | None] | None:
    """
    Return ``(name, value)`` if the statement assigns a single name, else None.
    """
    if (
        isinstance(statement, ast.Assign)
        and len(statement.targets) == 1
        and isinstance(statement.targets[0], ast.Name)
    ):
        return statement.targets[0].id, statement.value
    if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
        return statement.target.id, statement.value
    return None


def _char_offset(lines: list[str], lineno: int, col_offset: int) -> int:
    """
    Convert an ast position (1-based line, utf-8 byte column) into a string index.
    """
    prefix = sum(len(line) for line in lines[: lineno - 1])
    line_bytes = lines[lineno - 1].encode("utf-8")
    return prefix + len(line_bytes[:col_offset].decode("utf-8"))


def parse_python_implementation(code: str) -> ParsedPythonImplementation:
    """
    Parse the ``@input`` / ``@output`` annotations of a python implementation.

    :param code: The python source code.
    :return: The parsed interface and the rewritten code.
    :raises PythonAnnotationError: If the code or its annotations are invalid.
    """
    code = normalize_annotations(code)
    try:
        module = ast.parse(code)
        comments = [
            token
            for token in tokenize.generate_tokens(io.StringIO(code).readline)
            if token.type == tokenize.COMMENT
        ]
    except (SyntaxError, tokenize.TokenError) as ex:
        msg = f"Python implementation is not valid python code: {ex}"
        raise PythonAnnotationError(msg) from ex

    statements = module.body
    interface = PythonServiceInterface()
    # input assignments whose value becomes the default, keyed by statement
    defaults: dict[int, tuple[str, ast.expr]] = {}

    for comment in comments:
        match = _ANNOTATION_REGEX.match(comment.string.strip())
        if match is None:
            continue
        kind, rest = match.group(1), match.group(2).strip()
        line = comment.start[0]

        if rest:
            names = [x for x in _IDENTIFIER_SEPARATOR_REGEX.split(rest) if x]
            for name in names:
                if not name.isidentifier():
                    msg = f"Line {line}: '{name}' is not a valid variable name for @{kind}"
                    raise PythonAnnotationError(msg)
                if kind == "input":
                    _add_unique(interface.inputs, name)
                    _add_unique(interface.required_inputs, name)
                else:
                    _add_unique(interface.outputs, name)
            continue

        # annotation without names: attached to the assignment on the same or next line
        is_inline = comment.line[: comment.start[1]].strip() != ""
        statement = next(
            (
                s
                for s in statements
                if (
                    s.lineno <= line <= _end_lineno(s) if is_inline else s.lineno > line
                )
            ),
            None,
        )
        target = _assignment_target(statement) if statement is not None else None
        if target is None:
            msg = (
                f"Line {line}: @{kind} without variable names must be attached to "
                "an assignment of a single top-level variable"
            )
            raise PythonAnnotationError(msg)
        name, value = target
        if kind == "input":
            _add_unique(interface.inputs, name)
            if value is not None:
                defaults[id(statement)] = (name, value)
            else:
                _add_unique(interface.required_inputs, name)
        else:
            _add_unique(interface.outputs, name)

    return ParsedPythonImplementation(
        interface=interface,
        code=_rewrite_defaults(code, list(defaults.values())),
    )


def _end_lineno(statement: ast.stmt) -> int:
    return (
        statement.end_lineno if statement.end_lineno is not None else statement.lineno
    )


def _rewrite_defaults(code: str, defaults: list[tuple[str, ast.expr]]) -> str:
    """
    Replace ``x = <value>`` with ``x = __leqo_inputs__.get("x", <value>)``.
    """
    lines = code.splitlines(keepends=True)
    replacements: list[tuple[int, int, str]] = []
    for name, value in defaults:
        assert value.end_lineno is not None and value.end_col_offset is not None
        start = _char_offset(lines, value.lineno, value.col_offset)
        end = _char_offset(lines, value.end_lineno, value.end_col_offset)
        replacements.append(
            (start, end, f"{INPUTS_VARIABLE}.get({name!r}, {code[start:end]})")
        )

    for start, end, replacement in sorted(replacements, reverse=True):
        code = code[:start] + replacement + code[end:]
    return code


def detect_requirements(code: str) -> list[str]:
    """
    Best-effort detection of third-party packages imported by the code.
    """
    modules: set[str] = set()
    for statement in ast.walk(ast.parse(code)):
        if isinstance(statement, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in statement.names)
        elif (
            isinstance(statement, ast.ImportFrom)
            and statement.level == 0
            and statement.module
        ):
            modules.add(statement.module.split(".")[0])

    packages = {
        _PACKAGE_ALIASES.get(module, module)
        for module in modules
        if module not in sys.stdlib_module_names and module != "__future__"
    }
    packages.add("requests")
    return sorted(packages)


_SERVICE_TEMPLATE = '''"""
Camunda external task service generated by LEQO for node __NODE_ID__.

Fetches tasks of the topic in CAMUNDA_TOPIC, runs the implementation of the node
(see run_user_code) with the @input variables and completes the task with the
@output variables.
"""

import base64
import json
import os
import threading
import traceback

import requests

WORKER_ID = __WORKER_ID__
INPUTS = __INPUTS__
REQUIRED_INPUTS = __REQUIRED_INPUTS__
OUTPUTS = __OUTPUTS__
MAX_STRING_LENGTH = 4000
LOCK_DURATION = 100000000


def run_user_code(__leqo_inputs__):
    """
    Implementation of node __NODE_ID__.

    @input variables are read from the process variables of the task,
    @output variables are returned and written back when the task is completed.
    """
__INPUT_ASSIGNMENTS__
    # ----- user code -----
__USER_CODE__
    # ----- end of user code -----

    __leqo_locals__ = locals()
    missing = [name for name in OUTPUTS if name not in __leqo_locals__]
    if missing:
        raise RuntimeError("Output variables were not set: " + ", ".join(missing))
    return {name: __leqo_locals__[name] for name in OUTPUTS}


def read_variable(name, variable, process_instance_id):
    if variable.get("type") == "File":
        response = requests.get(
            camunda_endpoint
            + "/process-instance/"
            + process_instance_id
            + "/variables/"
            + name
            + "/data"
        )
        response.raise_for_status()
        return response.content.decode("utf-8")
    if variable.get("type") == "Json" and isinstance(variable.get("value"), str):
        return json.loads(variable["value"])
    return variable.get("value")


def to_camunda_variable(name, value):
    if hasattr(value, "tolist"):  # numpy arrays and scalars
        value = value.tolist()
    if value is None:
        return {"value": None, "type": "Null"}
    if isinstance(value, bool):
        return {"value": value, "type": "Boolean"}
    if isinstance(value, int):
        return {"value": value, "type": "Integer" if -(2**31) <= value < 2**31 else "Long"}
    if isinstance(value, float):
        return {"value": value, "type": "Double"}
    if not isinstance(value, str):
        try:
            value = json.dumps(value)
        except TypeError:
            value = str(value)
    if len(value) > MAX_STRING_LENGTH:
        # encode as file due to the string size limitation of camunda
        return {
            "value": base64.b64encode(value.encode("utf-8")).decode("utf-8"),
            "type": "File",
            "valueInfo": {"filename": name + ".txt", "encoding": "utf-8"},
        }
    return {"value": value, "type": "String"}


def handle_task(task):
    variables = task.get("variables") or {}
    process_instance_id = task.get("processInstanceId")
    inputs = {
        name: read_variable(name, variables[name], process_instance_id)
        for name in INPUTS
        if name in variables
    }
    missing = [name for name in REQUIRED_INPUTS if name not in inputs]
    if missing:
        raise RuntimeError("Missing input variables: " + ", ".join(missing))

    outputs = run_user_code(inputs)

    body = {
        "workerId": WORKER_ID,
        "variables": {name: to_camunda_variable(name, value) for name, value in outputs.items()},
    }
    response = requests.post(polling_endpoint + "/" + task["id"] + "/complete", json=body)
    print("Status code of response message: " + str(response.status_code))


def report_failure(task, error):
    body = {
        "workerId": WORKER_ID,
        "errorMessage": str(error)[:500],
        "errorDetails": traceback.format_exc(),
        "retries": 0,
        "retryTimeout": 0,
    }
    requests.post(polling_endpoint + "/" + task["id"] + "/failure", json=body)


def poll():
    print("Polling for new external tasks at the Camunda engine with URL: ", polling_endpoint)
    body = {
        "workerId": WORKER_ID,
        "maxTasks": 1,
        "topics": [{"topicName": topic, "lockDuration": LOCK_DURATION}],
    }
    try:
        response = requests.post(polling_endpoint + "/fetchAndLock", json=body)
        if response.status_code == 200:
            for task in response.json():
                print("External task with ID for topic " + str(task.get("topicName")) + ": " + str(task.get("id")))
                try:
                    handle_task(task)
                except Exception as ex:
                    traceback.print_exc()
                    report_failure(task, ex)
    except Exception:
        print("Exception during polling!")
        traceback.print_exc()

    threading.Timer(3, poll).start()


camunda_endpoint = os.environ["CAMUNDA_ENDPOINT"]
polling_endpoint = camunda_endpoint + "/external-task"
topic = os.environ.get("CAMUNDA_TOPIC", __TOPIC__)

if __name__ == "__main__":
    poll()
'''

_DOCKERFILE_TEMPLATE = """FROM python:3.12-slim

COPY service.zip /tmp/service.zip

RUN apt-get update && apt-get install -y unzip && rm -rf /var/lib/apt/lists/*
RUN unzip /tmp/service.zip -d /service
RUN pip install --no-cache-dir -r /service/requirements.txt

ENV CAMUNDA_TOPIC={topic}

CMD python /service/service.py
"""


def _indent_code(code: str, prefix: str) -> str:
    """
    Indent the code, except for lines inside multi-line string literals.
    """
    lines = code.splitlines()
    inside_string: set[int] = set()
    for node in ast.walk(ast.parse(code)):
        if (
            isinstance(node, ast.Constant | ast.JoinedStr)
            and node.end_lineno is not None
            and node.end_lineno > node.lineno
        ):
            inside_string.update(range(node.lineno + 1, node.end_lineno + 1))
    return "\n".join(
        line if index in inside_string or not line.strip() else prefix + line
        for index, line in enumerate(lines, start=1)
    )


def generate_service_code(
    node_id: str, topic: str, parsed: ParsedPythonImplementation
) -> str:
    """
    Generate the polling agent with the user code embedded into ``run_user_code``.

    :raises PythonAnnotationError: If the code cannot be embedded into a function.
    """
    interface = parsed.interface
    input_assignments = "".join(
        f"    {name} = {INPUTS_VARIABLE}[{name!r}]\n"
        for name in interface.required_inputs
    )
    user_code = _indent_code(
        parsed.code.replace("\r\n", "\n").replace("\r", "\n"), "    "
    )
    replacements = {
        "__NODE_ID__": node_id,
        "__WORKER_ID__": json.dumps(f"leqo-{python_service_topic(node_id)}"),
        "__INPUTS__": json.dumps(interface.inputs),
        "__REQUIRED_INPUTS__": json.dumps(interface.required_inputs),
        "__OUTPUTS__": json.dumps(interface.outputs),
        "__TOPIC__": json.dumps(topic),
        "__INPUT_ASSIGNMENTS__\n": input_assignments,
        # user code last, so placeholders in it are not replaced
        "__USER_CODE__": user_code if user_code.strip() else "    pass",
    }
    code = _SERVICE_TEMPLATE
    for key, value in replacements.items():
        code = code.replace(key, value)

    try:
        compile(code, "service.py", "exec")
    except SyntaxError as ex:
        msg = f"Python implementation cannot be embedded into the service: {ex}"
        raise PythonAnnotationError(msg) from ex
    return code


def _zip(files: dict[str, str | bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buffer.getvalue()


def generate_service_zip(node: ImplementationNode) -> bytes:
    """
    Generate the deployment model of one python node.

    Layout (same as the QuantME service examples)::

        Dockerfile
        service.zip
          ├── service.py        (polling agent with embedded python implementation)
          └── requirements.txt
    """
    parsed = parse_python_implementation(node.implementation)
    topic = python_service_topic(node.id)
    inner = _zip(
        {
            "service.py": generate_service_code(node.id, topic, parsed),
            "requirements.txt": "\n".join(detect_requirements(parsed.code))
            + "\n",
        }
    )
    return _zip(
        {
            "Dockerfile": _DOCKERFILE_TEMPLATE.format(topic=topic),
            "service.zip": inner,
        }
    )


def generate_service_deployment_models(nodes: list[Any]) -> bytes | None:
    """
    Generate a ZIP containing one ``<service task id>.zip`` per python node.

    :param nodes: Frontend nodes, non-python nodes are ignored.
        Python nodes inside the block of a repeat node are included.
    :return: The ZIP or None if there are no python nodes.
    """

    def flatten(nodes: list[Any]) -> list[Any]:
        result = []
        for node in nodes:
            result.append(node)
            block = getattr(node, "block", None)
            if block is not None:
                result.extend(flatten(block.nodes))
        return result

    python_nodes = [x for x in flatten(nodes) if is_python_implementation(x)]
    if not python_nodes:
        return None
    return _zip(
        {
            f"{python_service_task_id(node.id)}.zip": generate_service_zip(node)
            for node in python_nodes
        }
    )

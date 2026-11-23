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

_ANNOTATION_REGEX = re.compile(r"^#\s*@(input|output|property)\b(.*)$")
_BARE_ANNOTATION_REGEX = re.compile(
    r"^([ \t]*)(@(?:input|output|property|part)\b)", re.MULTILINE
)
_PART_REGEX = re.compile(r"^#[ \t]*@part\b[ \t]*(.*)$", re.MULTILINE)


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
    "neal": "dwave-neal",
    # not on PyPI: join order optimization of the SIGMOD 23 paper (reproduction package)
    "sigmod23_jo": "sigmod23-jo @ https://github.com/mehmet802/sigmod23-reproduction/archive/v0.1.0.zip",
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


def split_parts(code: str) -> list[tuple[str, str]]:
    """
    Split the code at ``# @part <label>`` lines into ``(label, code)`` parts.

    Code without ``@part`` lines is one part with an empty label.
    """
    code = normalize_annotations(code)
    matches = list(_PART_REGEX.finditer(code))
    if not matches:
        return [("", code)]
    parts = []
    if code[: matches[0].start()].strip():
        parts.append(("", code[: matches[0].start()]))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(code)
        parts.append((match.group(1).strip(), code[match.end() : end].lstrip("\n")))
    return parts


def parse_python_implementation(code: str) -> ParsedPythonImplementation:
    """
    Parse the ``@input`` / ``@output`` annotations of a python implementation.

    The code can consist of several parts (``# @part <label>``), e.g. blocks that pass
    objects to each other and therefore run in one service (see
    :mod:`app.transformation_manager.python_merge`). The parts run one after the other;
    a variable produced by a part is no input of the whole code for the later parts.

    :param code: The python source code.
    :return: The parsed interface and the rewritten code.
    :raises PythonAnnotationError: If the code or its annotations are invalid.
    """
    parts = split_parts(code)
    if len(parts) == 1:
        return _parse_part(parts[0][1])

    interface = PythonServiceInterface()
    produced: set[str] = set()
    codes: list[str] = []
    for label, part_code in parts:
        parsed = _parse_part(part_code)
        for name in parsed.interface.inputs:
            if name in produced:
                continue
            _add_unique(interface.inputs, name)
            if name in parsed.interface.required_inputs:
                _add_unique(interface.required_inputs, name)
        produced.update(parsed.interface.outputs)
        for name in parsed.interface.outputs:
            _add_unique(interface.outputs, name)

        section = f"# ----- part: {label} -----\n" if label else ""
        section += parsed.code.rstrip() + "\n"
        if produced:
            # inputs with default value of later parts take the produced values
            section += (
                "__leqo_part_locals__ = locals()\n"
                f"{INPUTS_VARIABLE}.update({{__leqo_name__: __leqo_part_locals__[__leqo_name__] "
                f"for __leqo_name__ in {sorted(produced)!r} "
                "if __leqo_name__ in __leqo_part_locals__})\n"
            )
        codes.append(section)
    return ParsedPythonImplementation(interface=interface, code="\n".join(codes))


_DATA_TYPE_NAMES = {
    "int",
    "float",
    "str",
    "bool",
    "list",
    "dict",
    "tuple",
    "None",
    "List",
    "Dict",
    "Tuple",
    "Optional",
    "Union",
    "Any",
}
"""Type hints of values that travel as process variables (numbers, strings, JSON)."""


def _is_data_annotation(annotation: ast.expr) -> bool:
    if isinstance(annotation, ast.Constant):
        if isinstance(annotation.value, str):  # "QuadraticProgram"
            try:
                return _is_data_annotation(ast.parse(annotation.value).body[0].value)  # type: ignore[attr-defined]
            except (SyntaxError, IndexError, AttributeError):
                return False
        return annotation.value is None
    if isinstance(annotation, ast.Name):
        return annotation.id in _DATA_TYPE_NAMES
    if isinstance(annotation, ast.Attribute):
        return annotation.attr in _DATA_TYPE_NAMES
    if isinstance(annotation, ast.Subscript):
        return _is_data_annotation(annotation.value)
    if isinstance(annotation, ast.BinOp):  # int | None
        return _is_data_annotation(annotation.left) and _is_data_annotation(
            annotation.right
        )
    return False


def _is_object_value(value: ast.expr) -> bool:
    """
    Whether the value is an object: the instance of a class (``QuadraticProgram()``,
    ``qp.Model(...)``) or a function.
    """
    if isinstance(value, ast.Lambda):
        return True
    if isinstance(value, ast.Call):
        func = value.func
        name = (
            func.id
            if isinstance(func, ast.Name)
            else func.attr
            if isinstance(func, ast.Attribute)
            else ""
        )
        return name[:1].isupper()
    return False


def _top_level_statements(statements: list[ast.stmt]) -> list[ast.stmt]:
    """Statements of the code incl. nested blocks, without functions and classes."""
    result = []
    for statement in statements:
        if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        result.append(statement)
        for name in ("body", "orelse", "finalbody"):
            result.extend(_top_level_statements(getattr(statement, name, [])))
        for handler in getattr(statement, "handlers", []):
            result.extend(_top_level_statements(handler.body))
    return result


def object_variables(code: str) -> set[str]:
    """
    Best-effort detection of the variables of the code that hold objects, which cannot
    be passed as process variables (numbers, strings, JSON).

    A variable is an object if it has a type hint other than a number, string, list or
    dict (``data: QuadraticProgram = ...``, also for inputs: ``data: QuadraticProgram``),
    or if it is assigned the instance of a class (``qp = QuadraticProgram()``).
    Values of other calls (``x = f()``) are not known and count as data.
    """
    try:
        module = ast.parse(normalize_annotations(code))
    except SyntaxError:
        return set()
    objects: set[str] = set()
    for statement in _top_level_statements(module.body):
        if isinstance(statement, ast.AnnAssign) and isinstance(
            statement.target, ast.Name
        ):
            if not _is_data_annotation(statement.annotation) or (
                statement.value is not None and _is_object_value(statement.value)
            ):
                objects.add(statement.target.id)
        elif isinstance(statement, ast.Assign) and _is_object_value(statement.value):
            objects.update(
                target.id
                for target in statement.targets
                if isinstance(target, ast.Name)
            )
    return objects


def _parse_part(code: str) -> ParsedPythonImplementation:
    """
    Parse the annotations of code without ``@part`` lines.
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
    properties = PythonServiceInterface()
    # input assignments whose value becomes the default, keyed by statement
    defaults: dict[int, tuple[str, ast.expr]] = {}

    for comment in comments:
        match = _ANNOTATION_REGEX.match(comment.string.strip())
        if match is None:
            continue
        kind, rest = match.group(1), match.group(2).strip()
        line = comment.start[0]
        # properties without value in the model (see resolve_properties) are inputs
        # after the other inputs (whose order matches the input ports of the node)
        target_interface = properties if kind == "property" else interface
        if kind == "property":
            kind = "input"

        if rest:
            names = [x for x in _IDENTIFIER_SEPARATOR_REGEX.split(rest) if x]
            for name in names:
                if not name.isidentifier():
                    msg = f"Line {line}: '{name}' is not a valid variable name for @{kind}"
                    raise PythonAnnotationError(msg)
                if kind == "input":
                    _add_unique(target_interface.inputs, name)
                    _add_unique(target_interface.required_inputs, name)
                else:
                    _add_unique(interface.outputs, name)
            continue

        # annotation without names: attached to the assignment on the same or next line
        statement = _attached_statement(statements, comment)
        target = _assignment_target(statement) if statement is not None else None
        if target is None:
            msg = (
                f"Line {line}: @{kind} without variable names must be attached to "
                "an assignment of a single top-level variable"
            )
            raise PythonAnnotationError(msg)
        name, value = target
        if kind == "input":
            _add_unique(target_interface.inputs, name)
            if value is not None:
                defaults[id(statement)] = (name, value)
            else:
                _add_unique(target_interface.required_inputs, name)
        else:
            _add_unique(interface.outputs, name)

    for name in properties.inputs:
        _add_unique(interface.inputs, name)
    for name in properties.required_inputs:
        _add_unique(interface.required_inputs, name)
    return ParsedPythonImplementation(
        interface=interface,
        code=_rewrite_defaults(code, list(defaults.values())),
    )


def _attached_statement(
    statements: list[ast.stmt], comment: tokenize.TokenInfo
) -> ast.stmt | None:
    """
    The top-level statement an annotation without names is attached to:
    the statement on the same line (inline comment) or the next statement.
    """
    line = comment.start[0]
    is_inline = comment.line[: comment.start[1]].strip() != ""
    return next(
        (
            s
            for s in statements
            if (s.lineno <= line <= _end_lineno(s) if is_inline else s.lineno > line)
        ),
        None,
    )


def _has_value(value: Any) -> bool:
    return value is not None and not (isinstance(value, str) and not value.strip())


def resolve_properties(code: str, values: dict[str, Any] | None) -> str:
    """
    Resolve the ``@property`` annotations with the property values of the node.

    Properties are configured in the model instead of being passed by other blocks::

        # @property graph_shape, num_relations   <- named properties
        # @property
        solver = "Simulated Annealing"            <- property with default value

    A property with a value in the model becomes an assignment of that value
    (``graph_shape = 'CHAIN'``, the default in the code is replaced). A property
    without value stays and is read like an ``@input`` from the variables of the
    workflow (with the default of the code, if any).

    :raises PythonAnnotationError: If the code or its annotations are invalid.
    """
    code = normalize_annotations(code)
    if "@property" not in code:
        return code
    values = {
        name: value for name, value in (values or {}).items() if _has_value(value)
    }
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

    lines = code.splitlines(keepends=True)
    line_starts = [0]
    for text in lines:
        line_starts.append(line_starts[-1] + len(text))
    edits: list[tuple[int, int, str]] = []

    for comment in comments:
        match = _ANNOTATION_REGEX.match(comment.string.strip())
        if match is None or match.group(1) != "property":
            continue
        line, column = comment.start
        start = line_starts[line - 1] + column
        end = start + len(comment.string)
        rest = match.group(2).strip()

        if rest:
            names = [x for x in _IDENTIFIER_SEPARATOR_REGEX.split(rest) if x]
            for name in names:
                if not name.isidentifier():
                    msg = f"Line {line}: '{name}' is not a valid variable name for @property"
                    raise PythonAnnotationError(msg)
            indent = comment.line[:column]
            if indent.strip():
                msg = f"Line {line}: @property with variable names must be on its own line"
                raise PythonAnnotationError(msg)
            new_lines = [
                f"{name} = {values[name]!r}  # property, value of the model"
                for name in names
                if name in values
            ]
            unset = [name for name in names if name not in values]
            if unset:
                new_lines.append("# @property " + ", ".join(unset))
            edits.append((start, end, ("\n" + indent).join(new_lines)))
            continue

        statement = _attached_statement(module.body, comment)
        target = _assignment_target(statement) if statement is not None else None
        if statement is None or target is None:
            msg = (
                f"Line {line}: @property without variable names must be attached to "
                "an assignment of a single top-level variable"
            )
            raise PythonAnnotationError(msg)
        name, value = target
        if name not in values:
            continue  # input of the workflow
        edits.append(
            (
                start,
                end,
                comment.string.replace("@property", "property, value of the model", 1),
            )
        )
        literal = repr(values[name])
        if value is not None:
            assert value.end_lineno is not None and value.end_col_offset is not None
            edits.append(
                (
                    _char_offset(lines, value.lineno, value.col_offset),
                    _char_offset(lines, value.end_lineno, value.end_col_offset),
                    literal,
                )
            )
        else:  # x: int
            assert statement.end_lineno is not None
            assert statement.end_col_offset is not None
            position = _char_offset(
                lines, statement.end_lineno, statement.end_col_offset
            )
            edits.append((position, position, " = " + literal))

    for start, end, replacement in sorted(edits, reverse=True):
        code = code[:start] + replacement + code[end:]
    return code


_ENVIRONMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def parse_environment(environment: dict[str, Any] | str | None) -> dict[str, str]:
    """
    Environment variables of the service container.

    :param environment: A dict or the content of a ``.env`` file
        (``NAME=VALUE`` lines, ``#`` comments, optional ``export`` and quotes).
    :raises PythonAnnotationError: If a line or name is invalid.
    """
    if not environment:
        return {}
    if isinstance(environment, dict):
        variables = {
            str(name): "" if value is None else str(value)
            for name, value in environment.items()
        }
    else:
        variables = {}
        for number, raw_line in enumerate(environment.splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            line = line.removeprefix("export ").strip()
            if "=" not in line:
                msg = f"Environment line {number}: expected NAME=VALUE"
                raise PythonAnnotationError(msg)
            name, value = (part.strip() for part in line.split("=", 1))
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":  # noqa: PLR2004
                value = value[1:-1]
            variables[name] = value
    for name in variables:
        if not _ENVIRONMENT_NAME.match(name):
            msg = f"'{name}' is not a valid name of an environment variable"
            raise PythonAnnotationError(msg)
    return variables


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


_REQUIREMENT_NAME = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")


def _normalize_package_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def merge_requirements(user_requirements: str | None, detected: list[str]) -> list[str]:
    """
    Combine the requirements file of the user with the detected packages.

    The lines of the user come first and win: a detected package is only added
    if the user did not already list it (e.g. with a pinned version).
    Comments and empty lines are dropped.
    """
    lines: list[str] = []
    user_packages: set[str] = set()
    for raw_line in (user_requirements or "").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        lines.append(line)
        match = _REQUIREMENT_NAME.match(line)
        if match:
            user_packages.add(_normalize_package_name(match.group(1)))

    lines.extend(
        package
        for package in detected
        if _requirement_name(package) not in user_packages
    )
    return lines


def _requirement_name(requirement: str) -> str:
    """Normalized package name of a requirement (``name @ url``, ``name==1.0``)."""
    match = _REQUIREMENT_NAME.match(requirement.strip())
    return _normalize_package_name(match.group(1) if match else requirement)


_SERVICE_TEMPLATE = '''"""
Camunda external task service generated by LEQO for node __NODE_ID__.

Fetches tasks of the topic in CAMUNDA_TOPIC, runs the implementation of the node
(see run_user_code) with the @input variables and completes the task with the
@output variables.
"""

import base64
import json
import os
import pickle
import time
import traceback

import requests

POLL_INTERVAL = 3
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
    value = variable.get("value")
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
        filename = (variable.get("valueInfo") or {}).get("filename") or ""
        if filename.endswith(".pickle"):
            # object written by a generated python service (see to_camunda_variable)
            return pickle.loads(response.content)
        content = response.content.decode("utf-8")
        if filename.endswith(".json"):
            return json.loads(content)
        return content
    if variable.get("type") == "Json" and isinstance(value, str):
        return json.loads(value)
    if isinstance(value, str) and value.strip()[:1] in ("[", "{"):
        # lists and dicts are written as JSON text in String variables
        try:
            return json.loads(value)
        except ValueError:
            pass
    return value


def _json_default(value):
    if hasattr(value, "tolist"):  # numpy arrays and scalars inside lists and dicts
        return value.tolist()
    raise TypeError("Object of type " + type(value).__name__ + " is not JSON serializable")


def _file_variable(content, filename, mime_type, encoding=None):
    value_info = {"filename": filename, "mimeType": mime_type}
    if encoding is not None:
        value_info["encoding"] = encoding
    return {
        "value": base64.b64encode(content).decode("utf-8"),
        "type": "File",
        "valueInfo": value_info,
    }


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
    filename = name + ".txt"
    mime_type = "text/plain"
    if not isinstance(value, str):
        try:
            value = json.dumps(value, default=_json_default)
            filename = name + ".json"
            mime_type = "application/json"
        except (TypeError, ValueError):
            # objects without JSON form (e.g. a Qiskit QuadraticProgram) are pickled,
            # so that a following python service gets the object back
            try:
                return _file_variable(
                    pickle.dumps(value), name + ".pickle", "application/x-python-pickle"
                )
            except Exception:
                value = str(value)
    if len(value) > MAX_STRING_LENGTH:
        # encode as file due to the string size limitation of camunda
        return _file_variable(value.encode("utf-8"), filename, mime_type, "utf-8")
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


def main():
    # Poll in the main thread: if the main thread ended and polling continued in
    # timer threads, the interpreter would already be shutting down and imports of
    # the user code (e.g. scipy -> concurrent.futures) would fail with
    # "can't register atexit after shutdown".
    while True:
        poll()
        time.sleep(POLL_INTERVAL)


camunda_endpoint = os.environ["CAMUNDA_ENDPOINT"]
polling_endpoint = camunda_endpoint + "/external-task"
topic = os.environ.get("CAMUNDA_TOPIC", __TOPIC__)

if __name__ == "__main__":
    main()
'''

_DOCKERFILE_TEMPLATE = """FROM python:3.12-slim

COPY service.zip /tmp/service.zip

RUN apt-get update && apt-get install -y unzip && rm -rf /var/lib/apt/lists/*
RUN unzip /tmp/service.zip -d /service
# packages without wheel for this python (e.g. qubovert) are compiled: the compiler is
# only installed if the installation fails without it
RUN pip install --no-cache-dir -r /service/requirements.txt \\
    || (apt-get update && apt-get install -y --no-install-recommends gcc g++ libc6-dev \\
        && rm -rf /var/lib/apt/lists/* \\
        && pip install --no-cache-dir -r /service/requirements.txt)

{environment}ENV CAMUNDA_TOPIC={topic}
ENV PYTHONUNBUFFERED=1

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


def _dockerfile_environment(environment: dict[str, Any] | str | None) -> str:
    """ENV lines of the environment variables (before the ones of the service)."""
    return "".join(
        f"ENV {name}={json.dumps(value)}\n"
        for name, value in parse_environment(environment).items()
    )


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
            "requirements.txt": "\n".join(
                merge_requirements(node.requirements, detect_requirements(parsed.code))
            )
            + "\n",
        }
    )
    return _zip(
        {
            "Dockerfile": _DOCKERFILE_TEMPLATE.format(
                topic=topic, environment=_dockerfile_environment(node.environment)
            ),
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

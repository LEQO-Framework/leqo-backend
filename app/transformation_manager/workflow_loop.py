"""
Support for :class:`~app.model.CompileRequest.RepeatNode` in workflows.

A repeat node becomes a loop in the workflow if it has a condition or contains
service nodes (python implementations, API connectors), as these cannot be unrolled
into OpenQASM. The loop is modelled with an exclusive gateway::

    ... -> (gateway) --condition--> task 1 -> ... -> task n --+
              ^  |                                            |
              |  +--default--> ...                            |
              +-----------------------------------------------+
"""

from __future__ import annotations

import re
from typing import Any

from app.model.CompileRequest import RepeatNode
from app.transformation_manager.api_connector import is_api_connector
from app.transformation_manager.python_service import is_python_implementation

_IDENTIFIER_REGEX = re.compile(r"[A-Za-z_]\w*")
_EXPRESSION_KEYWORDS = {
    "and",
    "or",
    "not",
    "true",
    "false",
    "null",
    "empty",
    "eq",
    "ne",
    "lt",
    "gt",
    "le",
    "ge",
    "div",
    "mod",
    "True",
    "False",
    "None",
}


def is_workflow_loop(node: object) -> bool:
    """
    Check whether the node is a repeat node that becomes a loop in the workflow.
    """
    return isinstance(node, RepeatNode) and (
        node.iterations is None
        or any(
            is_python_implementation(n) or is_api_connector(n) for n in node.block.nodes
        )
    )


def loop_gateway_id(node_id: str) -> str:
    """
    ID of the exclusive gateway that checks the loop condition.
    """
    return f"Task_{node_id}_gateway_loop"


def loop_condition_expression(node: RepeatNode) -> str:
    """
    The loop condition as Camunda (JUEL) expression.

    A repeat with a fixed number of iterations counts the iterations in a process variable.
    """
    if node.condition is None:
        return "${" + f"{loop_counter_variable(node.id)} < {node.iterations}" + "}"
    condition = node.condition.strip()
    if condition.startswith("${") and condition.endswith("}"):
        return condition
    return "${" + condition + "}"


def loop_counter_variable(node_id: str) -> str:
    """
    Name of the process variable counting the iterations of a repeat with fixed iterations.
    """
    return "loop_" + re.sub(r"\W", "_", node_id)


def condition_variables(node: RepeatNode) -> list[str]:
    """
    Variables referenced in the loop condition (best effort), in order of appearance.
    """
    if node.condition is None:
        return []
    # string literals do not contain variables
    condition = re.sub(r"(\"[^\"]*\"|'[^']*')", "", node.condition)
    names: list[str] = []
    for match in _IDENTIFIER_REGEX.finditer(condition):
        name = match.group(0)
        start = match.start()
        if start > 0 and (condition[start - 1].isdigit() or condition[start - 1] == "."):
            continue  # e.g. exponent of 1e5 or attribute access
        if name not in _EXPRESSION_KEYWORDS and name not in names:
            names.append(name)
    return names


def loop_body_order(node: RepeatNode) -> list[Any]:
    """
    The nodes of the loop body in topological order (edges from/to the repeat node are ignored).
    """
    body = {n.id: n for n in node.block.nodes if n.id != node.id}
    incoming: dict[str, set[str]] = {node_id: set() for node_id in body}
    for edge in node.block.edges:
        source, target = edge.source[0], edge.target[0]
        if source in body and target in body and source != target:
            incoming[target].add(source)

    order: list[Any] = []
    while incoming:
        ready = [node_id for node_id, preds in incoming.items() if not preds]
        if not ready:  # cycle, keep the remaining insertion order
            ready = list(incoming)
        for node_id in ready:
            order.append(body[node_id])
            del incoming[node_id]
        for preds in incoming.values():
            preds.difference_update(ready)
    return order

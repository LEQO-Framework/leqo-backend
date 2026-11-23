"""
Optimization loop for :class:`~app.model.CompileRequest.QAOANode` in workflows.

For the workflow target, a quantum group containing a QAOA node becomes one loop that
optimizes the parameters (gamma, beta) of the parametrized QAOA circuit with the
selected optimizer::

    +-> Set QAOA Parameters -> Compile (backend) -> Execute Job -> Get Results
    |       -> Optimize Parameters (python service)
    |       -> (converged or max iterations reached?) --yes--> Analyze Results
    +------------------------------------------------------no--+

* The first iteration uses the parameters of the QAOA node in the model.
* "Set QAOA Parameters" writes the current parameters into the QAOA node of the model,
  which is then compiled into OpenQASM by the backend and executed.
* "Optimize Parameters" is a generated python service (external task). It computes the
  value of the cost function from the measured counts and asks the optimizer for the
  next parameters, which are used at the start of the next iteration.
* The maximum number of iterations is an input of the workflow (start form).

The service is stateless: the evaluated parameters and costs are stored in a process
variable and the deterministic optimizer is replayed on this history to get the next
point (ask-and-tell on top of ``scipy.optimize.minimize``).
"""

from __future__ import annotations

import ast
import json
import re
from typing import Any

from app.model.CompileRequest import ImplementationNode, QAOANode

MAX_EVALUATIONS = 30
"""Maximum number of circuit evaluations of the optimization loop."""

MEASUREMENT_NODE_SUFFIX = "_qaoa_measurement"


def find_qaoa_node(nodes: list[Any]) -> QAOANode | None:
    """
    The first QAOA node of the nodes (dicts or frontend nodes), or None.
    """
    for node in nodes:
        if isinstance(node, QAOANode):
            return node
        if isinstance(node, dict) and node.get("type") == "qaoa":
            return QAOANode.model_validate(node)
    return None


def variable_prefix(qaoa_id: str) -> str:
    """
    Prefix of the process variables of the optimization loop of a QAOA node.
    """
    return "qaoa_" + re.sub(r"\W", "_", qaoa_id) + "_"


def optimizer_node_id(group_id: str) -> str:
    """
    ID of the (generated) python node that optimizes the parameters of a quantum group.
    """
    return f"{group_id}_qaoa_optimizer"


def converged_variable(qaoa_id: str) -> str:
    """
    Process variable that is true once the optimizer has converged.
    """
    return variable_prefix(qaoa_id) + "converged"


def iteration_variable(qaoa_id: str) -> str:
    """
    Process variable with the number of the current iteration of the loop.
    """
    return variable_prefix(qaoa_id) + "iteration"


def max_iterations_reached_variable(qaoa_id: str) -> str:
    """
    Process variable that is true once the maximum number of iterations is reached.
    """
    return variable_prefix(qaoa_id) + "max_iterations_reached"


def max_iterations_variable(qaoa_id: str) -> str:
    """
    Workflow input (start form) with the maximum number of iterations of the loop.
    """
    return variable_prefix(qaoa_id) + "maxIterations"


def loop_condition(qaoa_id: str) -> str:
    """
    Condition of the flow back to the start of the loop: neither converged nor the
    maximum number of iterations reached.
    """
    return (
        "${!"
        + converged_variable(qaoa_id)
        + " && !"
        + max_iterations_reached_variable(qaoa_id)
        + "}"
    )


def _parse_problem(qaoa: QAOANode) -> tuple[list[list[int]], int, bool]:
    # same interpretation of the edges as the QAOA enricher
    from app.enricher.qaoa import _parse_edges

    return _parse_edges(qaoa.edges, qaoa.problem)


def is_dimacs_problem(qaoa: QAOANode) -> bool:
    """
    Whether the edges are DIMACS literals (Max2SAT, 1-based, negative = negated).
    """
    return _parse_problem(qaoa)[2]


def _parameters(value: str, layers: int, default: float) -> list[float]:
    """
    Initial parameters, filled up like in the QAOA enricher.
    """
    try:
        parsed = [float(x.strip()) for x in value.split(",")] if value else []
    except ValueError:
        parsed = []
    fill = parsed[-1] if parsed else default
    return (parsed + [fill] * layers)[:layers]


def model_for_group(
    request: dict[str, Any],
    group_node_ids: set[str],
    qaoa: QAOANode,
) -> dict[str, Any]:
    """
    The model compiled in each iteration: the nodes of the quantum group and the data
    type nodes connected to them. If the group does not measure, all qubits of the QAOA
    are measured, as the optimizer needs the counts.
    """
    nodes = list(request.get("nodes", []))
    edges = list(request.get("edges", []))
    inputs = {
        edge["source"][0]
        for edge in edges
        if edge["target"][0] in group_node_ids
        and edge["source"][0] not in group_node_ids
    }
    keep = group_node_ids | {
        node["id"]
        for node in nodes
        if node["id"] in inputs and node.get("type") not in {"implementation"}
    }
    group_nodes = [node for node in nodes if node["id"] in keep]
    group_edges = [
        edge
        for edge in edges
        if edge["source"][0] in keep and edge["target"][0] in keep
    ]

    has_measurement = any(node.get("type") == "measure" for node in group_nodes)
    qaoa_output_used = any(edge["source"][0] == qaoa.id for edge in group_edges)
    if not has_measurement and not qaoa_output_used:
        _, num_qubits, _ = _parse_problem(qaoa)
        measurement_id = qaoa.id + MEASUREMENT_NODE_SUFFIX
        group_nodes.append(
            {
                "id": measurement_id,
                "type": "measure",
                "label": "QAOA Measurement",
                "indices": list(range(num_qubits)),
            }
        )
        group_edges.append({"source": [qaoa.id, 0], "target": [measurement_id, 0]})

    return {
        **request,
        "compilation_target": "qasm",
        "nodes": group_nodes,
        "edges": group_edges,
    }


def _groovy_string(value: str) -> str:
    """Escape a value for a single-quoted Groovy string."""
    return value.replace("\\", "\\\\").replace("'", "\\'").replace("$", "\\$")


_SET_PARAMETERS_SCRIPT = """import groovy.json.JsonSlurper
import groovy.json.JsonBuilder

// model of the quantum group with the QAOA node
def modelObj = new JsonSlurper().parseText('__MODEL__')

modelObj.nodes.each { node ->
    // placeholders of int nodes, as in the placeholder flow
    if (node.type == "int" && (node.value instanceof String)) {
        def placeholderValue = execution.getVariable(node.value)
        if (placeholderValue != null && placeholderValue.toString().trim() != "") {
            node.value = placeholderValue
        } else {
            throw new RuntimeException("Missing value for placeholder: " + node.value)
        }
    }
    // current parameters of the optimization loop (unset in the first iteration)
    if (node.id == "__QAOA_ID__") {
        def gamma = execution.getVariable("__PREFIX__gamma")
        def beta = execution.getVariable("__PREFIX__beta")
        if (gamma != null) {
            node.gamma = gamma.toString()
        }
        if (beta != null) {
            node.beta = beta.toString()
        }
        println "QAOA parameters: gamma=${node.gamma}, beta=${node.beta}"
    }
}

execution.setVariable("model", new JsonBuilder(modelObj).toPrettyString())

// number of the current iteration of the optimization loop (1 in the first one)
def iteration = execution.getVariable("__PREFIX__iteration")
iteration = iteration == null ? 1 : (iteration as int) + 1
execution.setVariable("__PREFIX__iteration", iteration)
println "QAOA iteration ${iteration} of ${execution.getVariable("__PREFIX__maxIterations")}"

// counter of the status polls of the compilation, reset in every iteration
execution.setVariable("iterations", 0)
"""


def set_parameters_script(model: dict[str, Any], qaoa: QAOANode) -> str:
    """
    Groovy script that writes the current parameters into the model to compile.
    """
    return (
        _SET_PARAMETERS_SCRIPT.replace("__MODEL__", _groovy_string(json.dumps(model)))
        .replace("__QAOA_ID__", qaoa.id)
        .replace("__PREFIX__", variable_prefix(qaoa.id))
    )


_OPTIMIZER_CODE = '''# Generated by LEQO: optimizes the parameters of the QAOA node __QAOA_ID__.
# @output __P__optimizer, __P__gamma, __P__beta, __P__converged, __P__max_iterations_reached
# @output __P__best_cost, __P__evaluations, __P__state
# @output __P__solution_bitstring, __P__solution_value, __P__partition
#
# The loop ends when the optimizer converged or __P__maxIterations circuits were
# evaluated (workflow input, defaults to __MAX_EVALUATIONS__).
#
# __P__solution_*: best sample measured in all iterations. For MaxCut: the bitstring
# (character i = node i), the cut value (number of cut edges) and the partition into
# the nodes with 0 and the nodes with 1. Max2SAT: the assignment and the number of
# satisfied clauses, GraphColoring: the coloring and the number of conflicts.
import json

import numpy as np
from scipy.optimize import minimize

# @input
resultExecution = None
# @input
__P__state = None
# @input
__P__maxIterations = None

PROBLEM = __PROBLEM__
OPTIMIZER = __OPTIMIZER__
OPTIMIZER_NAME = __OPTIMIZER_NAME__
LAYERS = __LAYERS__
EDGES = __EDGES__
NUM_QUBITS = __NUM_QUBITS__
IS_DIMACS = __IS_DIMACS__
INITIAL_PARAMETERS = __INITIAL_PARAMETERS__
SEED = 42


def max_evaluations(value):
    """Iteration budget of the loop: the workflow input, if it is a positive number."""
    try:
        budget = int(str(value).strip())
    except (TypeError, ValueError):
        return __MAX_EVALUATIONS__
    return budget if budget > 0 else __MAX_EVALUATIONS__


MAX_EVALUATIONS = max_evaluations(__P__maxIterations)


def parse_counts(raw):
    """Counts of the qunicorn results as {sample (int): count}."""
    results = json.loads(raw) if isinstance(raw, str) else raw
    if isinstance(results, dict):
        results = [results]
    for result in results or []:
        if not isinstance(result, dict):
            continue
        result_type = str(result.get("result_type", result.get("resultType", "")))
        if result_type.upper() != "COUNTS":
            continue
        registers = (result.get("metadata") or result.get("meta") or {}).get(
            "registers"
        ) or []
        counts = {}
        for key, value in (result.get("data") or {}).items():
            tokens = str(key).split()
            if not tokens:
                continue
            index = 0
            if len(tokens) > 1:
                # several classical registers: take the one measuring the QAOA qubits
                sizes = [register.get("size") for register in registers]
                if NUM_QUBITS in sizes and len(sizes) == len(tokens):
                    index = sizes.index(NUM_QUBITS)
            token = tokens[index]
            sample = int(token, 16) if token.startswith("0x") else int(token, 2)
            counts[sample] = counts.get(sample, 0) + value
        if counts:
            return counts
    raise RuntimeError("The execution result does not contain measurement counts")


def bit(sample, qubit):
    return (sample >> qubit) & 1


def literal(sample, value):
    """Truth value of a Max-2-SAT literal (a qubit in state 1 is true)."""
    if IS_DIMACS:
        return bit(sample, abs(value) - 1) == (1 if value > 0 else 0)
    return bit(sample, value) == 1


def cost(sample):
    """Cost of a measured sample, minimized by the optimizer."""
    if PROBLEM == "Max2SAT":
        return -sum(1 for u, v in EDGES if literal(sample, u) or literal(sample, v))
    if PROBLEM == "GraphColoring":
        return sum(1 for u, v in EDGES if bit(sample, u) == bit(sample, v))
    # MaxCut
    return -sum(1 for u, v in EDGES if bit(sample, u) != bit(sample, v))


def solution_value(sample):
    """Value of a sample: cut edges (MaxCut), satisfied clauses (Max2SAT), conflicts (GraphColoring)."""
    return cost(sample) if PROBLEM == "GraphColoring" else -cost(sample)


def best_sample(counts):
    """Measured sample with the lowest cost, the most frequent one on ties."""
    return min(counts, key=lambda sample: (cost(sample), -counts[sample]))


def expectation(counts):
    shots = sum(counts.values())
    return sum(count * cost(sample) for sample, count in counts.items()) / shots


class Ask(Exception):
    """Raised by the replayed objective at the first point without a known cost."""

    def __init__(self, point):
        super().__init__()
        self.point = [float(x) for x in point]


def spsa(objective, x0, iterations, rng):
    """
    Simultaneous perturbation stochastic approximation. Standard exponents, but larger
    steps than usual, as only few iterations fit into the evaluation budget.
    """
    x = np.array(x0, dtype=float)
    objective(x)  # like the scipy optimizers, start with the initial point
    for k in range(iterations):
        ak = 0.6 / (k + 1 + 3) ** 0.602
        ck = 0.1 / (k + 1) ** 0.101
        delta = rng.choice([-1.0, 1.0], size=len(x))
        plus = objective(x + ck * delta)
        minus = objective(x - ck * delta)
        x = x - ak * (plus - minus) / (2 * ck) * delta
    return x


state = __P__state
if isinstance(state, str):
    state = json.loads(state) if state.strip() else None
if not state:
    # the first circuit was executed with the initial parameters of the node
    state = {"history": [], "pending": INITIAL_PARAMETERS}

if state.get("pending") is not None:
    counts = parse_counts(resultExecution)
    state["history"].append([state["pending"], expectation(counts)])
    state["pending"] = None
    # best solution measured so far (over all iterations)
    sample = best_sample(counts)
    if state.get("best_sample") is None or cost(sample) < cost(state["best_sample"]):
        state["best_sample"] = sample

history = state["history"]


def objective(point):
    """
    Replays the optimizer: points that were already executed are answered with their
    known cost, the first new point is asked for. So every iteration of the loop
    executes a new parameter set, also if the optimizer revisits a point.
    """
    for known_point, known_cost in history:
        if np.allclose(point, known_point, rtol=0, atol=1e-12):
            return known_cost
    raise Ask(point)


next_point = None
if len(history) < MAX_EVALUATIONS:
    try:
        if OPTIMIZER == "SPSA":
            spsa(objective, INITIAL_PARAMETERS, MAX_EVALUATIONS // 2, np.random.default_rng(SEED))
        elif OPTIMIZER == "NELDER_MEAD":
            minimize(objective, np.array(INITIAL_PARAMETERS), method="Nelder-Mead", options={"maxfev": MAX_EVALUATIONS})
        else:
            minimize(objective, np.array(INITIAL_PARAMETERS), method="COBYLA", options={"maxiter": max(MAX_EVALUATIONS, len(INITIAL_PARAMETERS) + 2)})
    except Ask as ask:
        next_point = ask.point

best_point, best_cost = min(history, key=lambda entry: entry[1])
# stop: the optimizer converged, or the iteration budget is used up
__P__max_iterations_reached = next_point is None and len(history) >= MAX_EVALUATIONS
__P__converged = next_point is None and not __P__max_iterations_reached
if next_point is None:
    parameters = best_point
else:
    parameters = next_point
    state["pending"] = next_point

__P__gamma = ",".join(repr(float(x)) for x in parameters[:LAYERS])
__P__beta = ",".join(repr(float(x)) for x in parameters[LAYERS:])
__P__best_cost = float(best_cost)
__P__evaluations = len(history)
solution = state["best_sample"]
__P__solution_bitstring = "".join(str(bit(solution, q)) for q in range(NUM_QUBITS))
__P__solution_value = solution_value(solution)
# nodes (MaxCut, GraphColoring) or variables (Max2SAT, 1-based for DIMACS literals)
offset = 1 if IS_DIMACS else 0
__P__partition = [
    [q + offset for q in range(NUM_QUBITS) if bit(solution, q) == 0],
    [q + offset for q in range(NUM_QUBITS) if bit(solution, q) == 1],
]
__P__state = state
__P__optimizer = OPTIMIZER_NAME
print(
    "QAOA", OPTIMIZER_NAME, "iteration", len(history), "of", MAX_EVALUATIONS, "cost", history[-1][1],
    "best", best_cost, "converged", __P__converged,
    "max iterations reached", __P__max_iterations_reached,
)
'''


OPTIMIZER_NAMES = {"COBYLA": "COBYLA", "NELDER_MEAD": "Nelder-Mead", "SPSA": "SPSA"}
"""Display names of the optimizers selectable in the QAOA node."""


def optimizer_name(qaoa: QAOANode) -> str:
    """Display name of the optimizer selected in the QAOA node."""
    return OPTIMIZER_NAMES.get(qaoa.optimizer, qaoa.optimizer)


def optimizer_code(qaoa: QAOANode) -> str:
    """
    Python implementation (with @input/@output annotations) of the optimizer service.
    """
    edges, num_qubits, is_dimacs = _parse_problem(qaoa)
    initial = _parameters(qaoa.gamma, qaoa.p, 0.5) + _parameters(qaoa.beta, qaoa.p, 0.2)
    replacements = {
        "__QAOA_ID__": qaoa.id,
        "__PROBLEM__": repr(qaoa.problem),
        "__OPTIMIZER__": repr(qaoa.optimizer),
        "__OPTIMIZER_NAME__": repr(optimizer_name(qaoa)),
        "__LAYERS__": repr(qaoa.p),
        "__EDGES__": repr([list(edge) for edge in edges]),
        "__NUM_QUBITS__": repr(num_qubits),
        "__IS_DIMACS__": repr(is_dimacs),
        "__INITIAL_PARAMETERS__": repr(initial),
        "__MAX_EVALUATIONS__": repr(MAX_EVALUATIONS),
        "__P__": variable_prefix(qaoa.id),
    }
    code = _OPTIMIZER_CODE
    for key, value in replacements.items():
        code = code.replace(key, value)
    ast.parse(code)  # generated code must be valid
    return code


def optimizer_node(group_id: str, qaoa: QAOANode) -> ImplementationNode:
    """
    The python node of the optimizer service of a quantum group with a QAOA node.
    """
    return ImplementationNode(
        id=optimizer_node_id(group_id),
        label=f"Optimize QAOA Parameters ({optimizer_name(qaoa)})",
        language="python",
        implementation=optimizer_code(qaoa),
    )

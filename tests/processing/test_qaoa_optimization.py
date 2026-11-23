import asyncio
import io
import itertools
import json
import math
import os
import xml.etree.ElementTree as ET
import zipfile
from typing import Any

import pytest
from openqasm3.ast import QuantumGate
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from app.enricher import Enricher
from app.enricher.qaoa import QAOAEnricherStrategy, _parse_edges
from app.model.CompileRequest import CompileRequest, QAOANode
from app.transformation_manager import WorkflowProcessor
from app.transformation_manager.frontend_graph import FrontendGraph
from app.transformation_manager.python_service import (
    generate_service_code,
    parse_python_implementation,
    python_service_task_id,
    python_service_topic,
)
from app.transformation_manager.qaoa_optimization import (
    MAX_EVALUATIONS,
    MEASUREMENT_NODE_SUFFIX,
    iteration_variable,
    loop_condition,
    max_iterations_variable,
    model_for_group,
    optimizer_code,
    optimizer_node_id,
    variable_prefix,
)

BPMN = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"

QAOA = {
    "id": "qaoa-1",
    "type": "qaoa",
    "p": 1,
    "problem": "MaxCut",
    "optimizer": "COBYLA",
    "edges": "[[0, 1]]",
    "gamma": "0.5",
    "beta": "0.2",
    "outputIdentifier": "q",
}


def _request(qaoa: dict[str, Any]) -> CompileRequest:
    return CompileRequest.model_validate(
        {
            "metadata": {
                "version": "1.0.0",
                "name": "qaoa",
                "description": "",
                "author": "",
            },
            "compilation_target": "workflow",
            "nodes": [qaoa],
            "edges": [],
        }
    )


def _workflow(qaoa: dict[str, Any]) -> tuple[ET.Element, WorkflowProcessor]:
    request = _request(qaoa)
    graph = FrontendGraph.create(request.nodes, request.edges)
    workflow = WorkflowProcessor(
        Enricher(), graph, request.metadata, result="", original_request=request
    )
    bpmn = asyncio.run(workflow.process())
    assert bpmn, "BPMN generation failed"
    return ET.fromstring(bpmn), workflow


def test_workflow_contains_optimization_loop() -> None:
    root, workflow = _workflow(QAOA)
    process = root.find(f"{BPMN}process")
    assert process is not None
    elements = {el.get("id"): el for el in process if el.get("id")}

    group = "quantum_group_0"
    optimizer_task = python_service_task_id(optimizer_node_id(group))
    gateway_id = f"Task_{group}_gateway_optimize"
    set_parameters = f"Task_{group}_set_vars_1"
    assert optimizer_task in elements
    assert elements[set_parameters].get("name") == "Set QAOA Parameters"
    # the current iteration is counted at the start of the loop
    script = elements[set_parameters].find(f"{BPMN}script")
    assert script is not None
    assert f'setVariable("{iteration_variable(QAOA["id"])}", iteration)' in script.text

    flows = [
        (flow.get("sourceRef"), flow.get("targetRef"), flow)
        for flow in process.findall(f"{BPMN}sequenceFlow")
    ]
    pairs = {(src, tgt) for src, tgt, _ in flows}
    assert (f"Task_{group}_set_vars_2", optimizer_task) in pairs
    assert (optimizer_task, gateway_id) in pairs

    # not converged -> next iteration, default -> analyze the results
    loop_back = next(f for s, t, f in flows if s == gateway_id and t == set_parameters)
    condition = loop_back.find(f"{BPMN}conditionExpression")
    assert condition is not None
    assert condition.text == loop_condition(QAOA["id"])
    assert "converged" in condition.text
    assert "max_iterations_reached" in condition.text
    leave = next(f for s, t, f in flows if s == gateway_id and t != set_parameters)
    assert elements[gateway_id].get("default") == leave.get("id")
    assert leave.get("targetRef") == f"Task_{group}_human"

    # one loop: the start of the loop is entered once from the start event and
    # otherwise only from the gateway after the optimizer
    sources = sorted(s for s, t, _ in flows if t == set_parameters)
    assert sources == sorted([gateway_id, process.find(f"{BPMN}startEvent").get("id")])

    # max iterations is an input of the workflow
    start = process.find(f"{BPMN}startEvent")
    assert start is not None
    fields = {
        field.get("id"): field
        for field in start.iter("{http://camunda.org/schema/1.0/bpmn}formField")
    }
    field = fields[max_iterations_variable(QAOA["id"])]
    assert field.get("defaultValue") == str(MAX_EVALUATIONS)

    # the optimizer service is part of the service deployment models
    models = zipfile.ZipFile(io.BytesIO(workflow.service_deployment_models))
    assert f"{optimizer_task}.zip" in models.namelist()


def test_data_blocks_are_no_quantum_groups() -> None:
    """Array and bool blocks next to the QAOA do not execute the circuit again."""
    request = _request(QAOA).model_dump()
    request["nodes"] += [
        {"id": "gamma", "type": "array", "values": [0.5], "elementType": "float"},
        {"id": "beta", "type": "array", "values": [0.5], "elementType": "float"},
        {"id": "flag", "type": "bool", "value": True},
    ]
    request = CompileRequest.model_validate(request)
    graph = FrontendGraph.create(request.nodes, request.edges)
    workflow = WorkflowProcessor(
        Enricher(), graph, request.metadata, result="", original_request=request
    )
    root = ET.fromstring(asyncio.run(workflow.process()))
    names = [el.get("name") for el in root.iter() if el.get("name")]
    assert "Set Circuit" not in names
    assert names.count("Analyze Results") == 1


def test_model_for_group_adds_measurement() -> None:
    request = _request(QAOA).model_dump()
    model = model_for_group(request, {QAOA["id"]}, QAOANode.model_validate(QAOA))
    assert model["compilation_target"] == "qasm"
    measurement = next(n for n in model["nodes"] if n["type"] == "measure")
    assert measurement["id"] == QAOA["id"] + MEASUREMENT_NODE_SUFFIX
    assert measurement["indices"] == [0, 1]
    assert {"source": [QAOA["id"], 0], "target": [measurement["id"], 0]} in model[
        "edges"
    ]


def _service(qaoa: dict[str, Any]) -> Any:
    """The run_user_code function of the generated optimizer service."""
    node = QAOANode.model_validate(qaoa)
    parsed = parse_python_implementation(optimizer_code(node))
    code = generate_service_code("optimizer", python_service_topic("optimizer"), parsed)
    os.environ.setdefault("CAMUNDA_ENDPOINT", "http://localhost:8080/engine-rest")
    namespace: dict[str, Any] = {"__name__": "leqo_service"}
    exec(compile(code, "service.py", "exec"), namespace)
    return namespace["run_user_code"]


def _execute(gamma: float, beta: float) -> str:
    """
    Fake execution of the MaxCut QAOA of one edge: the probability to cut the edge
    depends on the parameters, the best parameters cut it in every shot.
    """
    shots = 1000
    cut = round(shots * math.sin(2 * beta) ** 2 * math.sin(gamma) ** 2)
    data = {"0x1": cut // 2, "0x2": cut - cut // 2, "0x0": shots - cut}
    return json.dumps(
        [
            {
                "result_type": "COUNTS",
                "data": data,
                "metadata": {"registers": [{"name": "c", "size": 2}]},
            }
        ]
    )


def _finished(outputs: dict[str, Any], prefix: str) -> bool:
    """Whether the gateway of the loop leaves the loop."""
    return bool(
        outputs[prefix + "converged"] or outputs[prefix + "max_iterations_reached"]
    )


@pytest.mark.parametrize("optimizer", ["COBYLA", "NELDER_MEAD", "SPSA"])
def test_max_iterations_input(optimizer: str) -> None:
    """The loop stops after maxIterations iterations (workflow input)."""
    qaoa = {**QAOA, "optimizer": optimizer}
    run = _service(qaoa)
    prefix = variable_prefix(qaoa["id"])
    max_iterations = 3

    gamma, beta, state = 0.5, 0.2, None
    for iteration in range(1, max_iterations + 1):
        outputs = run(
            {
                "resultExecution": _execute(gamma, beta),
                prefix + "state": state,
                prefix + "maxIterations": str(max_iterations),
            }
        )
        state = json.dumps(outputs[prefix + "state"])
        assert outputs[prefix + "evaluations"] == iteration
        assert _finished(outputs, prefix) == (iteration == max_iterations)
        gamma = float(outputs[prefix + "gamma"])
        beta = float(outputs[prefix + "beta"])

    assert outputs[prefix + "max_iterations_reached"]
    assert not outputs[prefix + "converged"]
    # the selected optimizer is shown in the results
    names = {"COBYLA": "COBYLA", "NELDER_MEAD": "Nelder-Mead", "SPSA": "SPSA"}
    assert outputs[prefix + "optimizer"] == names[optimizer]


def test_invalid_max_iterations_uses_default() -> None:
    run = _service(QAOA)
    prefix = variable_prefix(QAOA["id"])
    for value in ["", "abc", "0", None]:
        outputs = run(
            {
                "resultExecution": _execute(0.5, 0.2),
                prefix + "state": None,
                prefix + "maxIterations": value,
            }
        )
        assert not _finished(outputs, prefix)


@pytest.mark.parametrize("optimizer", ["COBYLA", "NELDER_MEAD", "SPSA"])
def test_optimizer_loop_converges(optimizer: str) -> None:
    qaoa = {**QAOA, "optimizer": optimizer}
    run = _service(qaoa)
    prefix = variable_prefix(qaoa["id"])

    gamma, beta = 0.5, 0.2  # initial parameters of the node
    initial_cost = None
    state = None
    executed: list[tuple[float, float]] = []
    for _ in range(MAX_EVALUATIONS + 1):
        # every iteration of the loop executes a new parameter set
        assert all(
            not math.isclose(gamma, g) or not math.isclose(beta, b) for g, b in executed
        ), f"parameters {(gamma, beta)} were already executed"
        executed.append((gamma, beta))
        outputs = run(
            {"resultExecution": _execute(gamma, beta), prefix + "state": state}
        )
        state = json.dumps(outputs[prefix + "state"])
        if initial_cost is None:
            initial_cost = outputs[prefix + "best_cost"]
        if _finished(outputs, prefix):
            break
        gamma = float(outputs[prefix + "gamma"])
        beta = float(outputs[prefix + "beta"])
    else:
        pytest.fail("optimization did not stop")

    assert outputs[prefix + "evaluations"] <= MAX_EVALUATIONS
    # cost is the negative expected cut, the optimizer found better parameters
    assert outputs[prefix + "best_cost"] < initial_cost
    # the best parameters are returned for the analysis
    best_gamma = float(outputs[prefix + "gamma"])
    best_beta = float(outputs[prefix + "beta"])
    best_cut = json.loads(_execute(best_gamma, best_beta))[0]["data"]
    assert -(best_cut["0x1"] + best_cut["0x2"]) / 1000 == pytest.approx(
        outputs[prefix + "best_cost"]
    )


def _counts(data: dict[str, int]) -> str:
    return json.dumps([{"result_type": "COUNTS", "data": data, "metadata": {}}])


PATH_MAX_CUT = 2
"""Maximum cut of the path graph 0 - 1 - 2."""


def test_maxcut_solution() -> None:
    qaoa = {**QAOA, "edges": "[[0, 1], [1, 2]]"}
    run = _service(qaoa)
    prefix = variable_prefix(qaoa["id"])

    # 0b010: node 1 on one side, nodes 0 and 2 on the other -> both edges cut
    outputs = run(
        {
            "resultExecution": _counts({"0x0": 500, "0x1": 300, "0x2": 200}),
            prefix + "state": None,
        }
    )
    assert outputs[prefix + "solution_bitstring"] == "010"
    assert outputs[prefix + "solution_value"] == PATH_MAX_CUT
    assert outputs[prefix + "partition"] == [[0, 2], [1]]

    # the best solution of all iterations is kept, also if later samples are worse
    outputs = run(
        {
            "resultExecution": _counts({"0x0": 900, "0x1": 100}),
            prefix + "state": json.dumps(outputs[prefix + "state"]),
        }
    )
    assert outputs[prefix + "solution_bitstring"] == "010"
    assert outputs[prefix + "solution_value"] == PATH_MAX_CUT


def test_analyze_results_shows_solution() -> None:
    root, _ = _workflow(QAOA)
    human = root.find(f".//{BPMN}userTask[@id='Task_quantum_group_0_human']")
    assert human is not None
    fields = {
        field.get("id")
        for field in human.iter("{http://camunda.org/schema/1.0/bpmn}formField")
    }
    prefix = variable_prefix(QAOA["id"])
    assert {
        prefix + "optimizer",
        prefix + "solution_bitstring",
        prefix + "solution_value",
        prefix + "partition",
    } <= fields


def _simulate(node: QAOANode) -> str:
    """
    Exact simulation of the circuit generated by the QAOA enricher,
    returned like the results of qunicorn (hex counts).
    """
    program = QAOAEnricherStrategy()._enrich_impl(node, None)[0].enriched_node
    num_qubits = _parse_edges(node.edges, node.problem)[1]
    circuit = QuantumCircuit(num_qubits)
    for gate in program.implementation.statements:
        if isinstance(gate, QuantumGate):
            qubits = [qubit.indices[0][0].value for qubit in gate.qubits]
            arguments = [argument.value for argument in gate.arguments]
            getattr(circuit, gate.name.name)(*arguments, *qubits)
    shots = 4000
    data = {
        f"0x{int(sample, 2):x}": round(probability * shots)
        for sample, probability in Statevector(circuit).probabilities_dict().items()
        if round(probability * shots) > 0
    }
    return json.dumps(
        [
            {
                "result_type": "COUNTS",
                "data": data,
                "metadata": {"registers": [{"name": "c", "size": num_qubits}]},
            }
        ]
    )


def _optimum(problem: str, edges: str) -> int:
    """Brute force: max cut / max satisfied clauses / min conflicts."""
    pairs, num_qubits, is_dimacs = _parse_edges(edges, problem)

    def value(bits: tuple[int, ...]) -> int:
        if problem == "MaxCut":
            return sum(bits[u] != bits[v] for u, v in pairs)
        if problem == "GraphColoring":
            return sum(bits[u] == bits[v] for u, v in pairs)

        def true(lit: int) -> bool:
            if is_dimacs:
                return bits[abs(lit) - 1] == (1 if lit > 0 else 0)
            return bits[lit] == 1

        return sum(true(u) or true(v) for u, v in pairs)

    values = [value(bits) for bits in itertools.product([0, 1], repeat=num_qubits)]
    return min(values) if problem == "GraphColoring" else max(values)


@pytest.mark.parametrize("optimizer", ["COBYLA", "NELDER_MEAD", "SPSA"])
@pytest.mark.parametrize(
    ("problem", "edges"),
    [
        ("MaxCut", "[[0, 1], [1, 2], [2, 3], [3, 0], [0, 2]]"),
        ("Max2SAT", "[[1, 2], [-1, 2], [1, -2], [-1, -3], [-2, 3]]"),  # DIMACS
        ("Max2SAT", "[[0, 1], [1, 2], [2, 3]]"),  # qubit indices
        ("GraphColoring", "[[0, 1], [1, 2], [2, 3], [3, 4]]"),
    ],
)
def test_optimization_of_simulated_qaoa(
    problem: str, edges: str, optimizer: str
) -> None:
    """The whole loop on the real QAOA circuits, for all problems and optimizers."""
    node = QAOANode.model_validate(
        {**QAOA, "problem": problem, "edges": edges, "optimizer": optimizer}
    )
    run = _service(node.model_dump())
    prefix = variable_prefix(node.id)

    state = None
    initial_cost = None
    for _ in range(MAX_EVALUATIONS + 1):
        outputs = run({"resultExecution": _simulate(node), prefix + "state": state})
        state = json.dumps(outputs[prefix + "state"])
        if initial_cost is None:
            initial_cost = outputs[prefix + "best_cost"]
        if _finished(outputs, prefix):
            break
        node = node.model_copy(
            update={
                "gamma": outputs[prefix + "gamma"],
                "beta": outputs[prefix + "beta"],
            }
        )
    else:
        pytest.fail("optimization did not stop")

    assert outputs[prefix + "best_cost"] < initial_cost
    assert outputs[prefix + "solution_value"] == _optimum(problem, edges)
    zeros, ones = outputs[prefix + "partition"]
    assert len(zeros) + len(ones) == len(outputs[prefix + "solution_bitstring"])

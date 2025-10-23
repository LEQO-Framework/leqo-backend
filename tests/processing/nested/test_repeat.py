import pytest

from app.enricher import ParsedImplementationNode
from app.model.CompileRequest import (
    Edge,
    GateNode,
    ImplementationNode,
    NestedBlock,
    RepeatNode,
)
from app.model.data_types import LeqoSupportedType, QubitType
from app.openqasm3.printer import leqo_dumps
from app.transformation_manager.frontend_graph import FrontendGraph
from app.transformation_manager.graph import ProgramNode
from app.transformation_manager.merge import merge_nodes
from app.transformation_manager.nested.repeat import unroll_repeat
from app.transformation_manager.nested.utils import generate_pass_node_implementation
from app.transformation_manager.utils import normalize_qasm_string
from tests.processing.nested.utils import H_IMPL, build_graph


async def assert_unroll_repeat(
    node: RepeatNode,
    requested_inputs: dict[int, LeqoSupportedType],
    expected: FrontendGraph,
) -> None:
    _entry_node, _exit_node, enrolled_graph = unroll_repeat(node, requested_inputs)
    actual_graph = await build_graph(enrolled_graph)
    actual = normalize_qasm_string(leqo_dumps(merge_nodes(actual_graph)))
    print(actual)
    expected_impl = normalize_qasm_string(
        leqo_dumps(merge_nodes(await build_graph(expected)))
    )
    assert expected_impl == actual


@pytest.mark.asyncio
async def test_single_node() -> None:
    requested_inputs: dict[int, LeqoSupportedType] = {0: QubitType(1)}
    node_id = "repeat_node"
    hex = ProgramNode(node_id).id.hex

    await assert_unroll_repeat(
        RepeatNode(
            id=node_id,
            iterations=2,
            block=NestedBlock(
                nodes=[ImplementationNode(id="h_node", implementation=H_IMPL)],
                edges=[
                    Edge(source=("h_node", 0), target=(node_id, 0)),
                    Edge(source=(node_id, 0), target=("h_node", 0)),
                ],
            ),
        ),
        requested_inputs=requested_inputs,
        expected=FrontendGraph.create(
            nodes=[
                ParsedImplementationNode(
                    id=f"leqo_{hex}_repeat_entry",
                    implementation=generate_pass_node_implementation(requested_inputs),
                ),
                ImplementationNode(
                    id=f"leqo_{hex}_repeat_0_h_node",
                    implementation=H_IMPL,
                ),
                ParsedImplementationNode(
                    id=f"leqo_{hex}_repeat_0_exit",
                    implementation=generate_pass_node_implementation(requested_inputs),
                ),
                ImplementationNode(
                    id=f"leqo_{hex}_repeat_1_h_node",
                    implementation=H_IMPL,
                ),
                ParsedImplementationNode(
                    id=node_id,
                    implementation=generate_pass_node_implementation(requested_inputs),
                ),
            ],
            edges=[
                Edge(
                    source=(f"leqo_{hex}_repeat_entry", 0),
                    target=(f"leqo_{hex}_repeat_0_h_node", 0),
                ),
                Edge(
                    source=(f"leqo_{hex}_repeat_0_h_node", 0),
                    target=(f"leqo_{hex}_repeat_0_exit", 0),
                ),
                Edge(
                    source=(f"leqo_{hex}_repeat_0_exit", 0),
                    target=(f"leqo_{hex}_repeat_1_h_node", 0),
                ),
                Edge(
                    source=(f"leqo_{hex}_repeat_1_h_node", 0),
                    target=(node_id, 0),
                ),
            ],
        ),
    )


@pytest.mark.asyncio
async def test_empty_repeat() -> None:
    requested_inputs: dict[int, LeqoSupportedType] = {0: QubitType(1)}
    node_id = "repeat_node"
    hex = ProgramNode(node_id).id.hex

    await assert_unroll_repeat(
        RepeatNode(
            id=node_id,
            iterations=2,
            block=NestedBlock(
                nodes=[],
                edges=[
                    Edge(source=(node_id, 0), target=(node_id, 0)),
                ],
            ),
        ),
        requested_inputs=requested_inputs,
        expected=FrontendGraph.create(
            nodes=[
                ParsedImplementationNode(
                    id=f"leqo_{hex}_repeat_entry",
                    implementation=generate_pass_node_implementation(requested_inputs),
                ),
                ParsedImplementationNode(
                    id=f"leqo_{hex}_repeat_0_exit",
                    implementation=generate_pass_node_implementation(requested_inputs),
                ),
                ParsedImplementationNode(
                    id=node_id,
                    implementation=generate_pass_node_implementation(requested_inputs),
                ),
            ],
            edges=[
                Edge(
                    source=(f"leqo_{hex}_repeat_entry", 0),
                    target=(f"leqo_{hex}_repeat_0_exit", 0),
                ),
                Edge(
                    source=(f"leqo_{hex}_repeat_0_exit", 0),
                    target=(node_id, 0),
                ),
            ],
        ),
    )


@pytest.mark.asyncio
async def test_complexer() -> None:
    requested_inputs: dict[int, LeqoSupportedType] = {0: QubitType(1), 1: QubitType(1)}
    node_id = "repeat_node"
    hex = ProgramNode(node_id).id.hex

    await assert_unroll_repeat(
        RepeatNode(
            id=node_id,
            iterations=3,
            block=NestedBlock(
                nodes=[
                    GateNode(id="h_node", gate="h"),
                    GateNode(id="cx_node", gate="cx"),
                ],
                edges=[
                    Edge(source=(node_id, 0), target=("h_node", 0)),
                    Edge(source=(node_id, 1), target=("cx_node", 0)),
                    Edge(source=("h_node", 0), target=("cx_node", 1)),
                    Edge(source=("cx_node", 0), target=(node_id, 1)),
                    Edge(source=("cx_node", 1), target=(node_id, 0)),
                ],
            ),
        ),
        requested_inputs=requested_inputs,
        expected=FrontendGraph.create(
            nodes=[
                ParsedImplementationNode(
                    id=f"leqo_{hex}_repeat_entry",
                    implementation=generate_pass_node_implementation(requested_inputs),
                ),
                GateNode(id=f"leqo_{hex}_repeat_0_h_node", gate="h"),
                GateNode(id=f"leqo_{hex}_repeat_0_cx_node", gate="cx"),
                ParsedImplementationNode(
                    id=f"leqo_{hex}_repeat_0_exit",
                    implementation=generate_pass_node_implementation(requested_inputs),
                ),
                GateNode(id=f"leqo_{hex}_repeat_1_h_node", gate="h"),
                GateNode(id=f"leqo_{hex}_repeat_1_cx_node", gate="cx"),
                ParsedImplementationNode(
                    id=f"leqo_{hex}_repeat_1_exit",
                    implementation=generate_pass_node_implementation(requested_inputs),
                ),
                GateNode(id=f"leqo_{hex}_repeat_2_h_node", gate="h"),
                GateNode(id=f"leqo_{hex}_repeat_2_cx_node", gate="cx"),
                ParsedImplementationNode(
                    id=node_id,
                    implementation=generate_pass_node_implementation(requested_inputs),
                ),
            ],
            edges=[
                Edge(
                    source=(f"leqo_{hex}_repeat_entry", 0),
                    target=(f"leqo_{hex}_repeat_0_h_node", 0),
                ),
                Edge(
                    source=(f"leqo_{hex}_repeat_entry", 1),
                    target=(f"leqo_{hex}_repeat_0_cx_node", 0),
                ),
                Edge(
                    source=(f"leqo_{hex}_repeat_0_h_node", 0),
                    target=(f"leqo_{hex}_repeat_0_cx_node", 1),
                ),
                Edge(
                    source=(f"leqo_{hex}_repeat_0_cx_node", 0),
                    target=(f"leqo_{hex}_repeat_0_exit", 1),
                ),
                Edge(
                    source=(f"leqo_{hex}_repeat_0_cx_node", 1),
                    target=(f"leqo_{hex}_repeat_0_exit", 0),
                ),
                Edge(
                    source=(f"leqo_{hex}_repeat_0_exit", 0),
                    target=(f"leqo_{hex}_repeat_1_h_node", 0),
                ),
                Edge(
                    source=(f"leqo_{hex}_repeat_0_exit", 1),
                    target=(f"leqo_{hex}_repeat_1_cx_node", 0),
                ),
                Edge(
                    source=(f"leqo_{hex}_repeat_1_h_node", 0),
                    target=(f"leqo_{hex}_repeat_1_cx_node", 1),
                ),
                Edge(
                    source=(f"leqo_{hex}_repeat_1_cx_node", 0),
                    target=(f"leqo_{hex}_repeat_1_exit", 1),
                ),
                Edge(
                    source=(f"leqo_{hex}_repeat_1_cx_node", 1),
                    target=(f"leqo_{hex}_repeat_1_exit", 0),
                ),
                Edge(
                    source=(f"leqo_{hex}_repeat_1_exit", 0),
                    target=(f"leqo_{hex}_repeat_2_h_node", 0),
                ),
                Edge(
                    source=(f"leqo_{hex}_repeat_1_exit", 1),
                    target=(f"leqo_{hex}_repeat_2_cx_node", 0),
                ),
                Edge(
                    source=(f"leqo_{hex}_repeat_2_h_node", 0),
                    target=(f"leqo_{hex}_repeat_2_cx_node", 1),
                ),
                Edge(
                    source=(f"leqo_{hex}_repeat_2_cx_node", 0),
                    target=(node_id, 1),
                ),
                Edge(
                    source=(f"leqo_{hex}_repeat_2_cx_node", 1),
                    target=(node_id, 0),
                ),
            ],
        ),
    )

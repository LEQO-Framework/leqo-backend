from app.model.CompileRequest import Edge, NestedBlock
from app.model.data_types import BitType, BoolType, IntType, QubitType
from app.openqasm3.printer import leqo_dumps
from app.transformation_manager.nested.utils import (
    generate_missing_qubit_pass_throughs,
    generate_pass_node_implementation,
)
from app.transformation_manager.utils import normalize_qasm_string


def test_pass_node_impl() -> None:
    actual = generate_pass_node_implementation(
        {0: QubitType(3), 1: IntType(32), 2: BitType(4), 3: BoolType()}
    )
    expected = """
        OPENQASM 3.1;
        @leqo.input 0
        qubit[3] pass_node_declaration_0;
        @leqo.output 0
        let pass_node_alias_0 = pass_node_declaration_0;
        @leqo.input 1
        int[32] pass_node_declaration_1;
        @leqo.output 1
        let pass_node_alias_1 = pass_node_declaration_1;
        @leqo.input 2
        bit[4] pass_node_declaration_2;
        @leqo.output 2
        let pass_node_alias_2 = pass_node_declaration_2;
        @leqo.input 3
        bool pass_node_declaration_3;
        @leqo.output 3
        let pass_node_alias_3 = pass_node_declaration_3;
        """
    assert normalize_qasm_string(expected) == normalize_qasm_string(leqo_dumps(actual))


def test_missing_qubit_pass_throughs() -> None:
    block = NestedBlock(
        nodes=[],
        edges=[
            Edge(source=("node", 0), target=("h", 0)),
            Edge(source=("h", 0), target=("node", 0)),
        ],
    )

    actual = generate_missing_qubit_pass_throughs(
        block, "node", {0: QubitType(1), 1: IntType(32), 2: QubitType(1)}
    )

    assert actual == [Edge(source=("node", 2), target=("node", 2))], (
        "Only a qubit input the block doesn't route out needs a pass-through edge."
    )

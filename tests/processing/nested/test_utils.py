from app.model.data_types import BitType, BoolType, IntType, QubitType
from app.openqasm3.printer import leqo_dumps
from app.processing.nested.utils import generate_pass_node_implementation
from app.processing.utils import normalize_qasm_string


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

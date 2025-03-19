from typing import Any

from openqasm3.ast import QASMNode
from openqasm3.parser import parse
from openqasm3.printer import dumps
from openqasm3.visitor import QASMTransformer

from app.lib.qasm_string import normalize
from app.preprocessing.split_reg_and_io_parse import SplitRegAndIOParse


def apply_transformer(program: str, trans: QASMTransformer[Any]) -> str:
    ast = parse(program)
    result = trans.visit(ast)
    if not isinstance(result, QASMNode):
        msg = f"Transformer {trans} returned non QASMNode: {result}"
        raise TypeError(msg)
    return dumps(result)


def test_split_qubit_declaration() -> None:
    before = """
    qubit[5] q;
    """
    expected = """
    qubit q_part0;
    qubit q_part1;
    qubit q_part2;
    qubit q_part3;
    qubit q_part4;
    """
    real = apply_transformer(before, SplitRegAndIOParse())
    print(normalize(real))
    assert normalize(expected) == normalize(real)


def test_parse_qubit_reg_annotation() -> None:
    pass


def test_split_unindexed_qubit_reg_gates() -> None:
    before = """
    qubit[3] q0;
    qubit q1;
    g0 q0;
    g1 q0, q1;
    """
    expected = """
    qubit q0_part0;
    qubit q0_part1;
    qubit q0_part2;
    qubit q1;
    g0 q0_part0;
    g0 q0_part1;
    g0 q0_part2;
    g1 q0_part0 q1;
    g1 q0_part1 q1;
    g1 q0_part2 q1;
    """
    real = apply_transformer(before, SplitRegAndIOParse())
    print(normalize(real))
    assert normalize(expected) == normalize(real)

def test_split_unindexed_qubit_reg_gates() -> None:
    before = """
    qubit[3] q0;
    qubit[3] q1;
    g0 q0[0:2:2];
    g1 q0[1:2], q1[0:1];
    """
    ast = parse(before)
    # breakpoint()
    expected = """
    qubit q0_part0;
    qubit q0_part1;
    qubit q0_part2;
    qubit q1_part0;
    qubit q1_part1;
    qubit q1_part2;
    g0 q0_part0;
    g0 q0_part2;
    """
    real = apply_transformer(before, SplitRegAndIOParse())
    print(normalize(real))
    assert normalize(expected) == normalize(real)

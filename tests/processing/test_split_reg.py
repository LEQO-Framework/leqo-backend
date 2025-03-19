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

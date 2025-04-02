from io import UnsupportedOperation

import pytest
from openqasm3.parser import parse

from app.processing.graph import (
    SingleInputInfo,
    SingleIOInfo,
    SingleOutputInfo,
    IOInfo,
)
from app.processing.pre.io_parser import IOParse
from app.processing.utils import normalize_qasm_string


def test_simple_input() -> None:
    code = """
    @leqo.input 0
    qubit[3] q;
    """
    expected = IOInfo(
        {"q": [0, 1, 2]},
        {},
        {
            0: SingleIOInfo(input=SingleInputInfo(0, 0)),
            1: SingleIOInfo(input=SingleInputInfo(0, 1)),
            2: SingleIOInfo(input=SingleInputInfo(0, 2)),
        },
    )
    actual = IOInfo()
    IOParse(actual).visit(parse(code))
    assert expected == actual


def test_output_simple() -> None:
    code = """
    qubit[3] q;

    @leqo.output 0
    let a = q;
    """
    expected = IOInfo(
        {"q": [0, 1, 2]},
        {"a": [0, 1, 2]},
        {
            0: SingleIOInfo(output=SingleOutputInfo(0, 0)),
            1: SingleIOInfo(output=SingleOutputInfo(0, 1)),
            2: SingleIOInfo(output=SingleOutputInfo(0, 2)),
        },
    )
    actual = IOInfo()
    IOParse(actual).visit(parse(code))
    assert expected == actual


def test_output_indexed() -> None:
    code = """
    qubit[3] q;

    @leqo.output 0
    let a = q[0:1];
    """
    expected = IOInfo(
        {"q": [0, 1, 2]},
        {"a": [0, 1]},
        {
            0: SingleIOInfo(output=SingleOutputInfo(0, 0)),
            1: SingleIOInfo(output=SingleOutputInfo(0, 1)),
            2: SingleIOInfo(),
        },
    )
    actual = IOInfo()
    IOParse(actual).visit(parse(code))
    assert expected == actual


def test_classical_ignored() -> None:
    code = """
    qubit[2] q;
    bit[2] c;

    let a = c;
    """
    expected = IOInfo(
        {
            "q": [0, 1],
        },
        {},
        {
            0: SingleIOInfo(),
            1: SingleIOInfo(),
        },
    )
    actual = IOInfo()
    IOParse(actual).visit(parse(code))
    assert expected == actual


def test_output_concatenation() -> None:
    code = """
    qubit[2] q0;
    qubit[2] q1;

    @leqo.output 0
    let a = q0[0] ++ q1[0];
    """
    expected = IOInfo(
        {
            "q0": [0, 1],
            "q1": [2, 3],
        },
        {"a": [0, 2]},
        {
            0: SingleIOInfo(output=SingleOutputInfo(0, 0)),
            1: SingleIOInfo(),
            2: SingleIOInfo(output=SingleOutputInfo(0, 1)),
            3: SingleIOInfo(),
        },
    )
    actual = IOInfo()
    IOParse(actual).visit(parse(code))
    assert expected == actual


def test_output_big_concatenation() -> None:
    code = """
    qubit[2] q0;
    qubit[2] q1;

    @leqo.output 0
    let a = q0[0] ++ q1[0] ++ q0[1];
    """
    expected = IOInfo(
        {
            "q0": [0, 1],
            "q1": [2, 3],
        },
        {"a": [0, 2, 1]},
        {
            0: SingleIOInfo(output=SingleOutputInfo(0, 0)),
            1: SingleIOInfo(output=SingleOutputInfo(0, 2)),
            2: SingleIOInfo(output=SingleOutputInfo(0, 1)),
            3: SingleIOInfo(),
        },
    )
    actual = IOInfo()
    IOParse(actual).visit(parse(code))
    assert expected == actual


def test_alias_chain() -> None:
    code = normalize_qasm_string("""
    qubit[5] q;

    let a = q[{4, 3, 2, 1, 0}]; // reverse order
    let b = a[{4, 3, 2, 1, 0}]; // reverse order back to normal
    let c = b[2:-1]; // get ids 2, 3, 4
    let d = c[1:2]; // get ids 3, 4
    @leqo.reusable
    let e = d[0]; // get id 3
    """)
    expected = IOInfo(
        {
            "q": [0, 1, 2, 3, 4],
        },
        {
            "a": [4, 3, 2, 1, 0],
            "b": [0, 1, 2, 3, 4],
            "c": [2, 3, 4],
            "d": [3, 4],
            "e": [3],
        },
        {
            0: SingleIOInfo(),
            1: SingleIOInfo(),
            2: SingleIOInfo(),
            3: SingleIOInfo(reusable=True),
            4: SingleIOInfo(),
        },
    )
    actual = IOInfo()
    IOParse(actual).visit(parse(code))
    assert expected == actual


def test_raise_on_missing_io_index() -> None:
    code = """
    @leqo.input 0
    qubit[2] q0;
    @leqo.input 2
    qubit[2] q1;
    """
    with pytest.raises(IndexError):
        IOParse(IOInfo()).visit(parse(code))


def test_raise_on_duplicate_declaration_annotation() -> None:
    code = """
    @leqo.input 0
    @leqo.input 1
    qubit[2] q0;
    """
    with pytest.raises(UnsupportedOperation):
        IOParse(IOInfo()).visit(parse(code))


def test_raise_on_duplicate_alias_annotation() -> None:
    code = """
    qubit[2] q0;

    @leqo.output 0
    @leqo.output 1
    let tmp = q0;
    """
    with pytest.raises(UnsupportedOperation):
        IOParse(IOInfo()).visit(parse(code))


def test_raise_on_input_annotation_over_alias() -> None:
    code = """
    qubit[2] q0;

    @leqo.input 0
    let tmp = q0;
    """
    with pytest.raises(UnsupportedOperation):
        IOParse(IOInfo()).visit(parse(code))


def test_raise_on_output_annotation_over_declaration() -> None:
    code = """
    @leqo.output 0
    qubit[2] q0;
    """
    with pytest.raises(UnsupportedOperation):
        IOParse(IOInfo()).visit(parse(code))


def test_raise_on_reusable_and_output() -> None:
    code = """
    qubit[5] q0;

    @leqo.output 0
    let a = q0[2];
    @leqo.reusable
    let b = q0[2];
    """
    with pytest.raises(UnsupportedOperation):
        IOParse(IOInfo()).visit(parse(code))


def test_raise_on_double_output_declaration_on_single_qubit() -> None:
    code = """
    qubit[5] q0;

    @leqo.output 0
    let a = q0[1];
    @leqo.output 1
    let b = q0[1];
    """
    with pytest.raises(UnsupportedOperation):
        IOParse(IOInfo()).visit(parse(code))


def test_all() -> None:
    code = normalize_qasm_string("""
    @leqo.input 0
    qubit[5] q0;
    @leqo.input 1
    qubit[5] q1;

    let a = q1[{4, 3, 2, 1, 0}];

    @leqo.output 0
    let _out0 = q0[0] ++ q1[0];
    @leqo.output 1
    let _out1 = q0[1] ++ a[1]; // a[1] == q1[3]

    @leqo.reusable
    let _reuse = q0[2:4];
    """)
    expected = IOInfo(
        {
            "q0": [0, 1, 2, 3, 4],
            "q1": [5, 6, 7, 8, 9],
        },
        {
            "a": [9, 8, 7, 6, 5],
            "_out0": [0, 5],
            "_out1": [1, 8],
            "_reuse": [2, 3, 4],
        },
        {
            0: SingleIOInfo(
                input=SingleInputInfo(0, 0),
                output=SingleOutputInfo(0, 0),
            ),
            1: SingleIOInfo(
                input=SingleInputInfo(0, 1),
                output=SingleOutputInfo(1, 0),
            ),
            2: SingleIOInfo(input=SingleInputInfo(0, 2), reusable=True),
            3: SingleIOInfo(input=SingleInputInfo(0, 3), reusable=True),
            4: SingleIOInfo(input=SingleInputInfo(0, 4), reusable=True),
            5: SingleIOInfo(
                input=SingleInputInfo(1, 0),
                output=SingleOutputInfo(0, 1),
            ),
            6: SingleIOInfo(input=SingleInputInfo(1, 1)),
            7: SingleIOInfo(input=SingleInputInfo(1, 2)),
            8: SingleIOInfo(
                input=SingleInputInfo(1, 3),
                output=SingleOutputInfo(1, 1),
            ),
            9: SingleIOInfo(input=SingleInputInfo(1, 4)),
        },
    )
    actual = IOInfo()
    IOParse(actual).visit(parse(code))
    assert expected == actual

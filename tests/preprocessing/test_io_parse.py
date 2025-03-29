from openqasm3.parser import parse

from app.lib.qasm_string import normalize
from app.model.dataclass import (
    SingleInputInfo,
    SingleIOInfo,
    SingleOutputInfo,
    SnippetIOInfo,
)
from app.preprocessing.io_parser import IOParse


def test_simple_input() -> None:
    code = """
    @leqo.input 0
    qubit[3] q;
    """
    expected = SnippetIOInfo(
        {"q": [0, 1, 2]},
        {},
        {
            0: SingleIOInfo(input=SingleInputInfo(0, 0)),
            1: SingleIOInfo(input=SingleInputInfo(0, 1)),
            2: SingleIOInfo(input=SingleInputInfo(0, 2)),
        },
    )
    actual = IOParse().extract_io_info(parse(code))
    assert expected == actual


def test_output_simple() -> None:
    code = """
    qubit[3] q;

    @leqo.output 0
    let a = q;
    """
    expected = SnippetIOInfo(
        {"q": [0, 1, 2]},
        {"a": [0, 1, 2]},
        {
            0: SingleIOInfo(output=SingleOutputInfo(0, 0)),
            1: SingleIOInfo(output=SingleOutputInfo(0, 1)),
            2: SingleIOInfo(output=SingleOutputInfo(0, 2)),
        },
    )
    actual = IOParse().extract_io_info(parse(code))
    assert expected == actual


def test_output_indexed() -> None:
    code = """
    qubit[3] q;

    @leqo.output 0
    let a = q[0:1];
    """
    expected = SnippetIOInfo(
        {"q": [0, 1, 2]},
        {"a": [0, 1]},
        {
            0: SingleIOInfo(output=SingleOutputInfo(0, 0)),
            1: SingleIOInfo(output=SingleOutputInfo(0, 1)),
            2: SingleIOInfo(),
        },
    )
    actual = IOParse().extract_io_info(parse(code))
    assert expected == actual


def test_output_concatenation() -> None:
    code = """
    qubit[2] q0;
    qubit[2] q1;

    @leqo.output 0
    let a = q0[0] ++ q1[0];
    """
    expected = SnippetIOInfo(
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
    actual = IOParse().extract_io_info(parse(code))
    assert expected == actual


def test_all() -> None:
    code = normalize("""
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
    expected = SnippetIOInfo(
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
    actual = IOParse().extract_io_info(parse(code))
    assert expected == actual

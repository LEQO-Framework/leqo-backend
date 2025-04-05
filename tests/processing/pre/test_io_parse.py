from io import UnsupportedOperation

import pytest
from openqasm3.parser import parse

from app.processing.graph import (
    IOInfo,
    QubitAnnotationInfo,
    QubitInputInfo,
    QubitOutputInfo,
)
from app.processing.pre.io_parser import IOParse
from app.processing.utils import normalize_qasm_string


def test_simple_input() -> None:
    code = """
    @leqo.input 0
    qubit[3] q;
    """
    expected = IOInfo(
        declaration_to_id={"q": [0, 1, 2]},
        id_to_info={
            0: QubitAnnotationInfo(input=QubitInputInfo(0, 0)),
            1: QubitAnnotationInfo(input=QubitInputInfo(0, 1)),
            2: QubitAnnotationInfo(input=QubitInputInfo(0, 2)),
        },
        input_to_ids={
            0: [0, 1, 2],
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
        declaration_to_id={"q": [0, 1, 2]},
        id_to_info={
            0: QubitAnnotationInfo(output=QubitOutputInfo(0, 0)),
            1: QubitAnnotationInfo(output=QubitOutputInfo(0, 1)),
            2: QubitAnnotationInfo(output=QubitOutputInfo(0, 2)),
        },
        output_to_ids={0: [0, 1, 2]},
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
        declaration_to_id={"q": [0, 1, 2]},
        id_to_info={
            0: QubitAnnotationInfo(output=QubitOutputInfo(0, 0)),
            1: QubitAnnotationInfo(output=QubitOutputInfo(0, 1)),
            2: QubitAnnotationInfo(),
        },
        output_to_ids={0: [0, 1]},
    )
    actual = IOInfo()
    IOParse(actual).visit(parse(code))
    assert expected == actual


def test_reusable() -> None:
    code = """
    qubit[3] q;

    @leqo.reusable 0
    let a = q[0:1];
    """
    expected = IOInfo(
        declaration_to_id={"q": [0, 1, 2]},
        id_to_info={
            0: QubitAnnotationInfo(reusable=True),
            1: QubitAnnotationInfo(reusable=True),
            2: QubitAnnotationInfo(),
        },
    )
    actual = IOInfo()
    IOParse(actual).visit(parse(code))
    assert expected == actual


def test_dirty() -> None:
    code = """
    @leqo.dirty
    qubit[3] q;
    """
    expected = IOInfo(
        declaration_to_id={"q": [0, 1, 2]},
        id_to_info={
            0: QubitAnnotationInfo(dirty=True),
            1: QubitAnnotationInfo(dirty=True),
            2: QubitAnnotationInfo(dirty=True),
        },
    )
    actual = IOInfo()
    IOParse(actual).visit(parse(code))
    assert expected == actual


def test_empty_index() -> None:
    code = """
    @leqo.input 0
    qubit q;
    """
    expected = IOInfo(
        declaration_to_id={"q": [0]},
        id_to_info={
            0: QubitAnnotationInfo(input=QubitInputInfo(0, 0)),
        },
        input_to_ids={0: [0]},
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
        declaration_to_id={
            "q": [0, 1],
        },
        id_to_info={
            0: QubitAnnotationInfo(),
            1: QubitAnnotationInfo(),
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
        declaration_to_id={
            "q0": [0, 1],
            "q1": [2, 3],
        },
        id_to_info={
            0: QubitAnnotationInfo(output=QubitOutputInfo(0, 0)),
            1: QubitAnnotationInfo(),
            2: QubitAnnotationInfo(output=QubitOutputInfo(0, 1)),
            3: QubitAnnotationInfo(),
        },
        output_to_ids={0: [0, 2]},
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
        declaration_to_id={
            "q0": [0, 1],
            "q1": [2, 3],
        },
        id_to_info={
            0: QubitAnnotationInfo(output=QubitOutputInfo(0, 0)),
            1: QubitAnnotationInfo(output=QubitOutputInfo(0, 2)),
            2: QubitAnnotationInfo(output=QubitOutputInfo(0, 1)),
            3: QubitAnnotationInfo(),
        },
        output_to_ids={0: [0, 2, 1]},
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
        declaration_to_id={
            "q": [0, 1, 2, 3, 4],
        },
        id_to_info={
            0: QubitAnnotationInfo(),
            1: QubitAnnotationInfo(),
            2: QubitAnnotationInfo(),
            3: QubitAnnotationInfo(reusable=True),
            4: QubitAnnotationInfo(),
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
    @leqo.dirty
    qubit q2;

    let a = q1[{4, 3, 2, 1, 0}];

    @leqo.output 0
    let _out0 = q0[0] ++ q1[0];
    @leqo.output 1
    let _out1 = q0[1] ++ a[1]; // a[1] == q1[3]

    @leqo.reusable
    let _reuse = q0[2:4];
    """)
    expected = IOInfo(
        declaration_to_id={
            "q0": [0, 1, 2, 3, 4],
            "q1": [5, 6, 7, 8, 9],
            "q2": [10],
        },
        id_to_info={
            0: QubitAnnotationInfo(
                input=QubitInputInfo(0, 0),
                output=QubitOutputInfo(0, 0),
            ),
            1: QubitAnnotationInfo(
                input=QubitInputInfo(0, 1),
                output=QubitOutputInfo(1, 0),
            ),
            2: QubitAnnotationInfo(input=QubitInputInfo(0, 2), reusable=True),
            3: QubitAnnotationInfo(input=QubitInputInfo(0, 3), reusable=True),
            4: QubitAnnotationInfo(input=QubitInputInfo(0, 4), reusable=True),
            5: QubitAnnotationInfo(
                input=QubitInputInfo(1, 0),
                output=QubitOutputInfo(0, 1),
            ),
            6: QubitAnnotationInfo(input=QubitInputInfo(1, 1)),
            7: QubitAnnotationInfo(input=QubitInputInfo(1, 2)),
            8: QubitAnnotationInfo(
                input=QubitInputInfo(1, 3),
                output=QubitOutputInfo(1, 1),
            ),
            9: QubitAnnotationInfo(input=QubitInputInfo(1, 4)),
            10: QubitAnnotationInfo(dirty=True),
        },
        input_to_ids={0: [0, 1, 2, 3, 4], 1: [5, 6, 7, 8, 9]},
        output_to_ids={0: [0, 5], 1: [1, 8]},
    )
    actual = IOInfo()
    IOParse(actual).visit(parse(code))
    assert expected == actual

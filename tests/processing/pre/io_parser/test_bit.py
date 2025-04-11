from io import UnsupportedOperation

import pytest
from openqasm3.parser import parse

from app.processing.io_info import (
    BitIOInfo,
    CombinedIOInfo,
    RegAnnotationInfo,
    RegSingleInputInfo,
    RegSingleOutputInfo,
)
from app.processing.pre.io_parser import ParseAnnotationsVisitor
from app.processing.utils import normalize_qasm_string


def test_simple_input() -> None:
    code = """
    @leqo.input 0
    bit[3] c;
    """
    expected = CombinedIOInfo(
        bit=BitIOInfo(
            declaration_to_ids={"c": [0, 1, 2]},
            id_to_info={
                0: RegAnnotationInfo(input=RegSingleInputInfo(0, 0)),
                1: RegAnnotationInfo(input=RegSingleInputInfo(0, 1)),
                2: RegAnnotationInfo(input=RegSingleInputInfo(0, 2)),
            },
            input_to_ids={
                0: [0, 1, 2],
            },
        ),
    )
    actual = CombinedIOInfo()
    ParseAnnotationsVisitor(actual).visit(parse(code))
    assert expected == actual


def test_output_simple() -> None:
    code = """
    bit[3] c;

    @leqo.output 0
    let a = c;
    """
    expected = CombinedIOInfo(
        bit=BitIOInfo(
            declaration_to_ids={"c": [0, 1, 2]},
            id_to_info={
                0: RegAnnotationInfo(output=RegSingleOutputInfo(0, 0)),
                1: RegAnnotationInfo(output=RegSingleOutputInfo(0, 1)),
                2: RegAnnotationInfo(output=RegSingleOutputInfo(0, 2)),
            },
            output_to_ids={0: [0, 1, 2]},
        ),
    )
    actual = CombinedIOInfo()
    ParseAnnotationsVisitor(actual).visit(parse(code))
    assert expected == actual


def test_output_indexed() -> None:
    code = """
    bit[3] c;

    @leqo.output 0
    let a = c[0:1];
    """
    expected = CombinedIOInfo(
        bit=BitIOInfo(
            declaration_to_ids={"c": [0, 1, 2]},
            id_to_info={
                0: RegAnnotationInfo(output=RegSingleOutputInfo(0, 0)),
                1: RegAnnotationInfo(output=RegSingleOutputInfo(0, 1)),
                2: RegAnnotationInfo(),
            },
            output_to_ids={0: [0, 1]},
        ),
    )
    actual = CombinedIOInfo()
    ParseAnnotationsVisitor(actual).visit(parse(code))
    assert expected == actual


def test_empty_index() -> None:
    code = """
    @leqo.input 0
    bit c;
    """
    expected = CombinedIOInfo(
        bit=BitIOInfo(
            declaration_to_ids={"c": [0]},
            id_to_info={
                0: RegAnnotationInfo(input=RegSingleInputInfo(0, 0)),
            },
            input_to_ids={0: [0]},
        ),
    )
    actual = CombinedIOInfo()
    ParseAnnotationsVisitor(actual).visit(parse(code))
    assert expected == actual


def test_output_concatenation() -> None:
    code = """
    bit[2] c0;
    bit[2] c1;

    @leqo.output 0
    let a = c0[0] ++ c1[0];
    """
    expected = CombinedIOInfo(
        bit=BitIOInfo(
            declaration_to_ids={
                "c0": [0, 1],
                "c1": [2, 3],
            },
            id_to_info={
                0: RegAnnotationInfo(output=RegSingleOutputInfo(0, 0)),
                1: RegAnnotationInfo(),
                2: RegAnnotationInfo(output=RegSingleOutputInfo(0, 1)),
                3: RegAnnotationInfo(),
            },
            output_to_ids={0: [0, 2]},
        ),
    )
    actual = CombinedIOInfo()
    ParseAnnotationsVisitor(actual).visit(parse(code))
    assert expected == actual


def test_output_big_concatenation() -> None:
    code = """
    bit[2] c0;
    bit[2] c1;

    @leqo.output 0
    let a = c0[0] ++ c1[0] ++ c0[1];
    """
    expected = CombinedIOInfo(
        bit=BitIOInfo(
            declaration_to_ids={
                "c0": [0, 1],
                "c1": [2, 3],
            },
            id_to_info={
                0: RegAnnotationInfo(output=RegSingleOutputInfo(0, 0)),
                1: RegAnnotationInfo(output=RegSingleOutputInfo(0, 2)),
                2: RegAnnotationInfo(output=RegSingleOutputInfo(0, 1)),
                3: RegAnnotationInfo(),
            },
            output_to_ids={0: [0, 2, 1]},
        ),
    )
    actual = CombinedIOInfo()
    ParseAnnotationsVisitor(actual).visit(parse(code))
    assert expected == actual


def test_alias_chain() -> None:
    code = normalize_qasm_string("""
    bit[5] c0;

    let a = c0[{4, 3, 2, 1, 0}]; // reverse order
    let b = a[{4, 3, 2, 1, 0}]; // reverse order back to normal
    let c = b[2:-1]; // get ids 2, 3, 4
    let d = c[1:2]; // get ids 3, 4
    @leqo.output 0
    let e = d[0]; // get id 3
    """)
    expected = CombinedIOInfo(
        bit=BitIOInfo(
            declaration_to_ids={
                "c0": [0, 1, 2, 3, 4],
            },
            id_to_info={
                0: RegAnnotationInfo(),
                1: RegAnnotationInfo(),
                2: RegAnnotationInfo(),
                3: RegAnnotationInfo(output=RegSingleOutputInfo(0, 0)),
                4: RegAnnotationInfo(),
            },
            output_to_ids={
                0: [3],
            },
        ),
    )
    actual = CombinedIOInfo()
    ParseAnnotationsVisitor(actual).visit(parse(code))
    assert expected == actual


def test_input_index_weird_order() -> None:
    code = """
    @leqo.input 1
    bit c1;
    @leqo.input 0
    bit c0;
    @leqo.input 2
    bit c2;
    """
    expected = CombinedIOInfo(
        bit=BitIOInfo(
            declaration_to_ids={
                "c1": [0],
                "c0": [1],
                "c2": [2],
            },
            id_to_info={
                0: RegAnnotationInfo(input=RegSingleInputInfo(1, 0)),
                1: RegAnnotationInfo(input=RegSingleInputInfo(0, 0)),
                2: RegAnnotationInfo(input=RegSingleInputInfo(2, 0)),
            },
            input_to_ids={
                0: [1],
                1: [0],
                2: [2],
            },
        ),
    )
    actual = CombinedIOInfo()
    ParseAnnotationsVisitor(actual).visit(parse(code))
    assert expected == actual


def test_all() -> None:
    code = normalize_qasm_string("""
    @leqo.input 0
    bit[5] c0;
    @leqo.input 1
    bit[5] c1;
    bit c2;

    let a = c1[{4, 3, 2, 1, 0}];

    @leqo.output 0
    let _out0 = c0[0] ++ c1[0];
    @leqo.output 1
    let _out1 = c0[1] ++ a[1]; // a[1] == c1[3]
    """)
    expected = CombinedIOInfo(
        bit=BitIOInfo(
            declaration_to_ids={
                "c0": [0, 1, 2, 3, 4],
                "c1": [5, 6, 7, 8, 9],
                "c2": [10],
            },
            id_to_info={
                0: RegAnnotationInfo(
                    input=RegSingleInputInfo(0, 0),
                    output=RegSingleOutputInfo(0, 0),
                ),
                1: RegAnnotationInfo(
                    input=RegSingleInputInfo(0, 1),
                    output=RegSingleOutputInfo(1, 0),
                ),
                2: RegAnnotationInfo(input=RegSingleInputInfo(0, 2)),
                3: RegAnnotationInfo(input=RegSingleInputInfo(0, 3)),
                4: RegAnnotationInfo(input=RegSingleInputInfo(0, 4)),
                5: RegAnnotationInfo(
                    input=RegSingleInputInfo(1, 0),
                    output=RegSingleOutputInfo(0, 1),
                ),
                6: RegAnnotationInfo(input=RegSingleInputInfo(1, 1)),
                7: RegAnnotationInfo(input=RegSingleInputInfo(1, 2)),
                8: RegAnnotationInfo(
                    input=RegSingleInputInfo(1, 3),
                    output=RegSingleOutputInfo(1, 1),
                ),
                9: RegAnnotationInfo(input=RegSingleInputInfo(1, 4)),
                10: RegAnnotationInfo(),
            },
            input_to_ids={0: [0, 1, 2, 3, 4], 1: [5, 6, 7, 8, 9]},
            output_to_ids={0: [0, 5], 1: [1, 8]},
        ),
    )
    actual = CombinedIOInfo()
    ParseAnnotationsVisitor(actual).visit(parse(code))
    assert expected == actual


def test_raise_on_missing_input_index() -> None:
    code = """
    @leqo.input 0
    bit[2] c0;
    @leqo.input 2
    bit[2] c1;
    """
    with pytest.raises(
        IndexError,
        match="Unsupported: Missing input index 1, next index was 2",
    ):
        ParseAnnotationsVisitor(CombinedIOInfo()).visit(parse(code))


def test_raise_on_missing_output_index() -> None:
    code = """
    bit[2] c0;
    bit[2] c1;

    @leqo.output 0
    let a = c0;
    @leqo.output 2
    let b = c1;
    """
    with pytest.raises(
        IndexError,
        match="Unsupported: Missing output index 1, next index was 2",
    ):
        ParseAnnotationsVisitor(CombinedIOInfo()).visit(parse(code))


def test_raise_on_duplicate_input_index() -> None:
    code = """
    @leqo.input 0
    bit[2] c0;
    @leqo.input 0
    bit[2] c1;
    """
    with pytest.raises(
        IndexError,
        match="Unsupported: duplicate input id: 0",
    ):
        ParseAnnotationsVisitor(CombinedIOInfo()).visit(parse(code))


def test_raise_on_duplicate_output_index() -> None:
    code = """
    bit[2] c0;
    bit[2] c1;

    @leqo.output 0
    let a = c0;
    @leqo.output 0
    let b = c1;
    """
    with pytest.raises(
        IndexError,
        match="Unsupported: duplicate output id: 0",
    ):
        ParseAnnotationsVisitor(CombinedIOInfo()).visit(parse(code))


def test_raise_on_output_index_not_starting_at_zero() -> None:
    code = """
    bit[2] c0;
    bit[2] c1;

    @leqo.output 1
    let a = c0;
    @leqo.output 2
    let b = c1;
    """
    with pytest.raises(
        IndexError,
        match="Unsupported: Missing output index 0, next index was 1",
    ):
        ParseAnnotationsVisitor(CombinedIOInfo()).visit(parse(code))


def test_raise_on_input_index_not_starting_at_zero() -> None:
    code = """
    @leqo.input 1
    bit[2] c0;
    @leqo.input 2
    bit[2] c1;
    """
    with pytest.raises(
        IndexError,
        match="Unsupported: Missing input index 0, next index was 1",
    ):
        ParseAnnotationsVisitor(CombinedIOInfo()).visit(parse(code))


def test_raise_on_reusable() -> None:
    code = """
    bit[2] c1;

    @leqo.reusable
    let a = c1;
    """
    with pytest.raises(
        UnsupportedOperation,
        match="Unsupported: reusable annotation over alias a referring to bits",
    ):
        ParseAnnotationsVisitor(CombinedIOInfo()).visit(parse(code))


def test_raise_on_dirty() -> None:
    code = """
    @leqo.dirty
    bit[2] c1;
    """
    with pytest.raises(
        UnsupportedOperation,
        match="Unsupported: dirty annotation over non-qubit declaration c1",
    ):
        ParseAnnotationsVisitor(CombinedIOInfo()).visit(parse(code))


def test_raise_on_duplicate_declaration_annotation() -> None:
    code = """
    @leqo.input 0
    @leqo.input 1
    bit[2] c0;
    """
    with pytest.raises(
        UnsupportedOperation,
        match="Unsupported: two input annotations over c0",
    ):
        ParseAnnotationsVisitor(CombinedIOInfo()).visit(parse(code))


def test_raise_on_duplicate_alias_annotation() -> None:
    code = """
    bit[2] c0;

    @leqo.output 0
    @leqo.output 1
    let tmp = c0;
    """
    with pytest.raises(
        UnsupportedOperation,
        match="Unsupported: two output annotations over tmp",
    ):
        ParseAnnotationsVisitor(CombinedIOInfo()).visit(parse(code))


def test_raise_on_input_annotation_over_alias() -> None:
    code = """
    bit[2] c0;

    @leqo.input 0
    let tmp = c0;
    """
    with pytest.raises(
        UnsupportedOperation,
        match="Unsupported: leqo.input annotations over AliasStatement tmp",
    ):
        ParseAnnotationsVisitor(CombinedIOInfo()).visit(parse(code))


def test_raise_on_output_annotation_over_declaration() -> None:
    code = """
    @leqo.output 0
    bit[2] c0;
    """
    with pytest.raises(
        UnsupportedOperation,
        match="Unsupported: leqo.output annotations over QubitDeclaration c0",
    ):
        ParseAnnotationsVisitor(CombinedIOInfo()).visit(parse(code))


def test_raise_on_double_output_declaration_on_single_bit() -> None:
    code = """
    bit[5] c0;

    @leqo.output 0
    let a = c0[1];
    @leqo.output 1
    let b = c0[1];
    """
    with pytest.raises(
        UnsupportedOperation,
        match="alias b tries to overwrite already declared output",
    ):
        ParseAnnotationsVisitor(CombinedIOInfo()).visit(parse(code))

from io import UnsupportedOperation

import pytest
from openqasm3.parser import parse

from app.processing.io_info import (
    BoolIOInfo,
    CombinedIOInfo,
    FloatIOInfo,
    IntIOInfo,
    SizedAnnotationInfo,
    SizedSingleInputInfo,
    SizedSingleOutputInfo,
)
from app.processing.pre.io_parser import ParseAnnotationsVisitor
from app.processing.utils import normalize_qasm_string


def test_simple_input() -> None:
    code = """
    @leqo.input 0
    int[32] i;
    """
    expected = CombinedIOInfo(
        int=IntIOInfo(
            declaration_to_id={"i": 0},
            id_to_info={
                0: SizedAnnotationInfo(input=SizedSingleInputInfo(0), size=32),
            },
            input_to_id={
                0: 0,
            },
        ),
    )
    actual = CombinedIOInfo()
    ParseAnnotationsVisitor(actual).visit(parse(code))
    assert expected == actual


def test_output_simple() -> None:
    code = """
    int[16] i;

    @leqo.output 0
    let a = i;
    """
    expected = CombinedIOInfo(
        int=IntIOInfo(
            declaration_to_id={"i": 0},
            id_to_info={
                0: SizedAnnotationInfo(output=SizedSingleOutputInfo(0), size=16),
            },
            output_to_id={0: 0},
        ),
    )
    actual = CombinedIOInfo()
    ParseAnnotationsVisitor(actual).visit(parse(code))
    assert expected == actual


def test_int_default() -> None:
    code = """
    @leqo.input 0
    int i;
    """
    expected = CombinedIOInfo(
        int=IntIOInfo(
            declaration_to_id={"i": 0},
            id_to_info={
                0: SizedAnnotationInfo(input=SizedSingleInputInfo(0), size=32),
            },
            input_to_id={
                0: 0,
            },
        ),
    )
    actual = CombinedIOInfo()
    ParseAnnotationsVisitor(actual).visit(parse(code))
    assert expected == actual


def test_float_default() -> None:
    code = """
    @leqo.input 0
    float f;
    """
    expected = CombinedIOInfo(
        float=FloatIOInfo(
            declaration_to_id={"f": 0},
            id_to_info={
                0: SizedAnnotationInfo(input=SizedSingleInputInfo(0), size=32),
            },
            input_to_id={
                0: 0,
            },
        ),
    )
    actual = CombinedIOInfo()
    ParseAnnotationsVisitor(actual).visit(parse(code))
    assert expected == actual


def test_bool_default() -> None:
    code = """
    @leqo.input 0
    bool b;
    """
    expected = CombinedIOInfo(
        bool=BoolIOInfo(
            declaration_to_id={"b": 0},
            id_to_info={
                0: SizedAnnotationInfo(input=SizedSingleInputInfo(0), size=1),
            },
            input_to_id={
                0: 0,
            },
        ),
    )
    actual = CombinedIOInfo()
    ParseAnnotationsVisitor(actual).visit(parse(code))
    assert expected == actual


def test_alias_chain() -> None:
    code = normalize_qasm_string("""
    int[32] i;

    let a = i;
    let b = a;
    let c = b;
    let d = c;
    @leqo.output 0
    let e = d;
    """)
    expected = CombinedIOInfo(
        int=IntIOInfo(
            declaration_to_id={
                "i": 0,
            },
            id_to_info={
                0: SizedAnnotationInfo(output=SizedSingleOutputInfo(0), size=32),
            },
            output_to_id={0: 0},
        ),
    )
    actual = CombinedIOInfo()
    ParseAnnotationsVisitor(actual).visit(parse(code))
    assert expected == actual


def test_input_index_weird_order() -> None:
    code = """
    @leqo.input 1
    int i1;
    @leqo.input 0
    int i0;
    @leqo.input 2
    int i2;
    """
    expected = CombinedIOInfo(
        int=IntIOInfo(
            declaration_to_id={
                "i1": 0,
                "i0": 1,
                "i2": 2,
            },
            id_to_info={
                0: SizedAnnotationInfo(input=SizedSingleInputInfo(1), size=32),
                1: SizedAnnotationInfo(input=SizedSingleInputInfo(0), size=32),
                2: SizedAnnotationInfo(input=SizedSingleInputInfo(2), size=32),
            },
            input_to_id={
                0: 1,
                1: 0,
                2: 2,
            },
        ),
    )
    actual = CombinedIOInfo()
    ParseAnnotationsVisitor(actual).visit(parse(code))
    assert expected == actual


def test_raise_on_missing_input_index() -> None:
    code = """
    @leqo.input 0
    int[2] i0;
    @leqo.input 2
    int[2] i1;
    """
    with pytest.raises(
        IndexError,
        match="Unsupported: Missing input index 1, next index was 2",
    ):
        ParseAnnotationsVisitor(CombinedIOInfo()).visit(parse(code))


def test_raise_on_missing_output_index() -> None:
    code = """
    int[2] i0;
    int[2] i1;

    @leqo.output 0
    let a = i0;
    @leqo.output 2
    let b = i1;
    """
    with pytest.raises(
        IndexError,
        match="Unsupported: Missing output index 1, next index was 2",
    ):
        ParseAnnotationsVisitor(CombinedIOInfo()).visit(parse(code))


def test_raise_on_duplicate_input_index() -> None:
    code = """
    @leqo.input 0
    int[2] i0;
    @leqo.input 0
    int[2] i1;
    """
    with pytest.raises(
        IndexError,
        match="Unsupported: duplicate input id: 0",
    ):
        ParseAnnotationsVisitor(CombinedIOInfo()).visit(parse(code))


def test_raise_on_duplicate_output_index() -> None:
    code = """
    int[2] i0;
    int[2] i1;

    @leqo.output 0
    let a = i0;
    @leqo.output 0
    let b = i1;
    """
    with pytest.raises(
        IndexError,
        match="Unsupported: duplicate output id: 0",
    ):
        ParseAnnotationsVisitor(CombinedIOInfo()).visit(parse(code))


def test_raise_on_input_index_not_starting_at_zero() -> None:
    code = """
    @leqo.input 1
    int[2] i0;
    @leqo.input 2
    int[2] i1;
    """
    with pytest.raises(
        IndexError,
        match="Unsupported: Missing input index 0, next index was 1",
    ):
        ParseAnnotationsVisitor(CombinedIOInfo()).visit(parse(code))


def test_raise_on_output_index_not_starting_at_zero() -> None:
    code = """
    int[2] i0;
    int[2] i1;

    @leqo.output 1
    let a = i0;
    @leqo.output 2
    let b = i1;
    """
    with pytest.raises(
        IndexError,
        match="Unsupported: Missing output index 0, next index was 1",
    ):
        ParseAnnotationsVisitor(CombinedIOInfo()).visit(parse(code))


def test_raise_on_reusable() -> None:
    code = """
    int[32] i1;

    @leqo.reusable
    let a = i1;
    """
    with pytest.raises(
        UnsupportedOperation,
        match="Unsupported: reusable annotation over alias a referring to classical",
    ):
        ParseAnnotationsVisitor(CombinedIOInfo()).visit(parse(code))


def test_raise_on_dirty() -> None:
    code = """
    @leqo.dirty
    int[32] i1;
    """
    with pytest.raises(
        UnsupportedOperation,
        match="Unsupported: dirty annotation over non-qubit declaration i1",
    ):
        ParseAnnotationsVisitor(CombinedIOInfo()).visit(parse(code))


def test_raise_on_duplicate_declaration_annotation() -> None:
    code = """
    @leqo.input 0
    @leqo.input 1
    int[2] i0;
    """
    with pytest.raises(
        UnsupportedOperation,
        match="Unsupported: two input annotations over i0",
    ):
        ParseAnnotationsVisitor(CombinedIOInfo()).visit(parse(code))


def test_raise_on_duplicate_alias_annotation() -> None:
    code = """
    int[2] i0;

    @leqo.output 0
    @leqo.output 1
    let tmp = i0;
    """
    with pytest.raises(
        UnsupportedOperation,
        match="Unsupported: two output annotations over tmp",
    ):
        ParseAnnotationsVisitor(CombinedIOInfo()).visit(parse(code))


def test_raise_on_input_annotation_over_alias() -> None:
    code = """
    int[2] i0;

    @leqo.input 0
    let tmp = i0;
    """
    with pytest.raises(
        UnsupportedOperation,
        match="Unsupported: leqo.input annotations over AliasStatement tmp",
    ):
        ParseAnnotationsVisitor(CombinedIOInfo()).visit(parse(code))


def test_raise_on_output_annotation_over_declaration() -> None:
    code = """
    @leqo.output 0
    int[2] i0;
    """
    with pytest.raises(
        UnsupportedOperation,
        match="Unsupported: leqo.output annotations over QubitDeclaration i0",
    ):
        ParseAnnotationsVisitor(CombinedIOInfo()).visit(parse(code))


def test_raise_on_double_output_declaration_on_single_qubit() -> None:
    code = """
    int[5] i0;

    @leqo.output 0
    let a = i0;
    @leqo.output 1
    let b = i0;
    """
    with pytest.raises(
        UnsupportedOperation,
        match="alias b tries to overwrite already declared output",
    ):
        ParseAnnotationsVisitor(CombinedIOInfo()).visit(parse(code))

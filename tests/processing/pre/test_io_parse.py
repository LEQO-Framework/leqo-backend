import re
from io import UnsupportedOperation

import pytest
from openqasm3.ast import BitType, BoolType, IntType
from openqasm3.parser import parse

from app.processing.graph import (
    ClassicalIOInstance,
    IOInfo,
    QubitInfo,
    QubitIOInstance,
)
from app.processing.pre.io_parser import ParseAnnotationsVisitor
from app.processing.utils import normalize_qasm_string


def test_simple_input() -> None:
    code = """
    @leqo.input 0
    qubit[3] q;
    """
    expected = (
        IOInfo(
            inputs={0: QubitIOInstance("q", [0, 1, 2])},
        ),
        QubitInfo(
            declaration_to_ids={"q": [0, 1, 2]},
            returned_dirty_ids=[0, 1, 2],
        ),
    )
    actual = (IOInfo(), QubitInfo())
    ParseAnnotationsVisitor(*actual).visit(parse(code))
    assert expected == actual


def test_output_simple() -> None:
    code = """
    qubit[3] q;

    @leqo.output 0
    let a = q;
    """
    expected = (
        IOInfo(
            outputs={0: QubitIOInstance("a", [0, 1, 2])},
        ),
        QubitInfo(
            declaration_to_ids={"q": [0, 1, 2]},
            required_reusable_ids=[0, 1, 2],
        ),
    )
    actual = (IOInfo(), QubitInfo())
    ParseAnnotationsVisitor(*actual).visit(parse(code))
    assert expected == actual


def test_output_indexed() -> None:
    code = """
    qubit[3] q;

    @leqo.output 0
    let a = q[0:1];
    """
    expected = (
        IOInfo(
            outputs={0: QubitIOInstance("a", [0, 1])},
        ),
        QubitInfo(
            declaration_to_ids={"q": [0, 1, 2]},
            required_reusable_ids=[0, 1, 2],
            returned_dirty_ids=[2],
        ),
    )
    actual = (IOInfo(), QubitInfo())
    ParseAnnotationsVisitor(*actual).visit(parse(code))
    assert expected == actual


def test_reusable() -> None:
    code = """
    qubit[3] q;

    @leqo.reusable
    let a = q[0:1];
    """
    expected = (
        IOInfo(),
        QubitInfo(
            declaration_to_ids={"q": [0, 1, 2]},
            required_reusable_ids=[0, 1, 2],
            returned_reusable_ids=[0, 1],
            returned_dirty_ids=[2],
        ),
    )
    actual = (IOInfo(), QubitInfo())
    ParseAnnotationsVisitor(*actual).visit(parse(code))
    assert expected == actual


def test_reusable_in_uncompute() -> None:
    code = """
    qubit[3] q;

    @leqo.uncompute
    if (false) {
        @leqo.reusable
        let a = q[0:1];
    }
    """
    expected = (
        IOInfo(),
        QubitInfo(
            declaration_to_ids={"q": [0, 1, 2]},
            required_reusable_ids=[0, 1, 2],
            returned_uncomputable_ids=[0, 1],
            returned_dirty_ids=[2],
        ),
    )
    actual = (IOInfo(), QubitInfo())
    ParseAnnotationsVisitor(*actual).visit(parse(code))
    assert expected == actual


def test_dirty() -> None:
    code = """
    @leqo.dirty
    qubit[3] q;
    """
    expected = (
        IOInfo(),
        QubitInfo(
            declaration_to_ids={"q": [0, 1, 2]},
            required_dirty_ids=[0, 1, 2],
            returned_dirty_ids=[0, 1, 2],
        ),
    )
    actual = (IOInfo(), QubitInfo())
    ParseAnnotationsVisitor(*actual).visit(parse(code))
    assert expected == actual


def test_spaces_tabs_on_dirty_or_reusable() -> None:
    code = """
    @leqo.dirty   
    qubit[3] q0;
    @leqo.dirty\t
    qubit[3] q1;

    @leqo.reusable   
    let a = q0;
    @leqo.reusable\t
    let b = q1;
    """
    ParseAnnotationsVisitor(IOInfo(), QubitInfo()).visit(parse(code))


def test_empty_index() -> None:
    code = """
    @leqo.input 0
    qubit q;
    """
    expected = (
        IOInfo(
            inputs={0: QubitIOInstance("q", [0])},
        ),
        QubitInfo(
            declaration_to_ids={"q": [0]},
            returned_dirty_ids=[0],
        ),
    )
    actual = (IOInfo(), QubitInfo())
    ParseAnnotationsVisitor(*actual).visit(parse(code))
    assert expected == actual


def test_classical_ignored() -> None:
    code = """
    qubit[2] q;
    bit[2] c;

    let a = c;
    """
    expected = (
        IOInfo(),
        QubitInfo(
            declaration_to_ids={"q": [0, 1]},
            required_reusable_ids=[0, 1],
            returned_dirty_ids=[0, 1],
        ),
    )
    actual = (IOInfo(), QubitInfo())
    ParseAnnotationsVisitor(*actual).visit(parse(code))
    assert expected == actual


def test_output_concatenation() -> None:
    code = """
    qubit[2] q0;
    qubit[2] q1;

    @leqo.output 0
    let a = q0[0] ++ q1[0];
    """
    expected = (
        IOInfo(
            outputs={0: QubitIOInstance("a", [0, 2])},
        ),
        QubitInfo(
            declaration_to_ids={
                "q0": [0, 1],
                "q1": [2, 3],
            },
            required_reusable_ids=[0, 1, 2, 3],
            returned_dirty_ids=[1, 3],
        ),
    )
    actual = (IOInfo(), QubitInfo())
    ParseAnnotationsVisitor(*actual).visit(parse(code))
    assert expected == actual


def test_output_big_concatenation() -> None:
    code = """
    qubit[2] q0;
    qubit[2] q1;

    @leqo.output 0
    let a = q0[0] ++ q1[0] ++ q0[1];
    """
    expected = (
        IOInfo(
            outputs={0: QubitIOInstance("a", [0, 2, 1])},
        ),
        QubitInfo(
            declaration_to_ids={
                "q0": [0, 1],
                "q1": [2, 3],
            },
            required_reusable_ids=[0, 1, 2, 3],
            returned_dirty_ids=[3],
        ),
    )
    actual = (IOInfo(), QubitInfo())
    ParseAnnotationsVisitor(*actual).visit(parse(code))
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
    expected = (
        IOInfo(),
        QubitInfo(
            declaration_to_ids={"q": [0, 1, 2, 3, 4]},
            required_reusable_ids=[0, 1, 2, 3, 4],
            returned_reusable_ids=[3],
            returned_dirty_ids=[0, 1, 2, 4],
        ),
    )
    actual = (IOInfo(), QubitInfo())
    ParseAnnotationsVisitor(*actual).visit(parse(code))
    assert expected == actual


def test_input_index_weird_order() -> None:
    code = """
    @leqo.input 1
    qubit q1;
    @leqo.input 0
    qubit q0;
    @leqo.input 2
    qubit q2;
    """
    expected = (
        IOInfo(
            inputs={
                0: QubitIOInstance("q0", [1]),
                1: QubitIOInstance("q1", [0]),
                2: QubitIOInstance("q2", [2]),
            },
        ),
        QubitInfo(
            declaration_to_ids={
                "q1": [0],
                "q0": [1],
                "q2": [2],
            },
            returned_dirty_ids=[0, 1, 2],
        ),
    )
    actual = (IOInfo(), QubitInfo())
    ParseAnnotationsVisitor(*actual).visit(parse(code))
    assert expected == actual


def test_classical() -> None:
    code = """
    @leqo.input 0
    bit[4] c0;
    @leqo.input 1
    int i;
    @leqo.input 2
    bool b;
    bit[8] c1;

    @leqo.output 0
    let out = c0[0:1] ++ c1[7:-2:0];
    """
    expected = (
        IOInfo(
            inputs={
                0: ClassicalIOInstance("c0", BitType, 4),
                1: ClassicalIOInstance("i", IntType, 32),
                2: ClassicalIOInstance("b", BoolType, 1),
            },
            outputs={0: ClassicalIOInstance("out", BitType, 6)},
        ),
        QubitInfo(),
    )
    actual = (IOInfo(), QubitInfo())
    ParseAnnotationsVisitor(*actual).visit(parse(code))
    assert expected == actual


def test_all() -> None:
    code = normalize_qasm_string("""
    @leqo.input 0
    qubit[5] q0;
    @leqo.input 1
    qubit[5] q1;
    @leqo.input 2
    int i;
    @leqo.dirty
    qubit q2;

    let a = q1[{4, 3, 2, 1, 0}];

    @leqo.output 0
    let _out0 = q0[0] ++ q1[0];
    @leqo.output 1
    let _out1 = q0[1] ++ a[1]; // a[1] == q1[3]
    @leqo.output 2
    let _out2 = i;

    @leqo.reusable
    let _reuse = q0[2:4];
    @leqo.uncompute
    if (false) {
        @leqo.reusable
        let _uncomputed = q1[4];
    }
    """)
    expected = (
        IOInfo(
            inputs={
                0: QubitIOInstance("q0", [0, 1, 2, 3, 4]),
                1: QubitIOInstance("q1", [5, 6, 7, 8, 9]),
                2: ClassicalIOInstance("i", IntType, 32),
            },
            outputs={
                0: QubitIOInstance("_out0", [0, 5]),
                1: QubitIOInstance("_out1", [1, 8]),
                2: ClassicalIOInstance("_out2", IntType, 32),
            },
        ),
        QubitInfo(
            declaration_to_ids={
                "q0": [0, 1, 2, 3, 4],
                "q1": [5, 6, 7, 8, 9],
                "q2": [10],
            },
            required_dirty_ids=[10],
            returned_reusable_ids=[2, 3, 4],
            returned_uncomputable_ids=[9],
            returned_dirty_ids=[6, 7, 10],
        ),
    )
    actual = (IOInfo(), QubitInfo())
    ParseAnnotationsVisitor(*actual).visit(parse(code))
    assert expected == actual


def test_raise_on_missing_input_index() -> None:
    code = """
    @leqo.input 0
    qubit[2] q0;
    @leqo.input 2
    qubit[2] q1;
    """
    with pytest.raises(
        IndexError,
        match="Unsupported: Missing input index 1, next index was 2",
    ):
        ParseAnnotationsVisitor(IOInfo(), QubitInfo()).visit(parse(code))


def test_raise_on_missing_output_index() -> None:
    code = """
    qubit[2] q0;
    qubit[2] q1;

    @leqo.output 0
    let a = q0;
    @leqo.output 2
    let b = q1;
    """
    with pytest.raises(
        IndexError,
        match="Unsupported: Missing output index 1, next index was 2",
    ):
        ParseAnnotationsVisitor(IOInfo(), QubitInfo()).visit(parse(code))


def test_raise_on_duplicate_input_index() -> None:
    code = """
    @leqo.input 0
    qubit[2] q0;
    @leqo.input 0
    qubit[2] q1;
    """
    with pytest.raises(
        IndexError,
        match="Unsupported: duplicate input id: 0",
    ):
        ParseAnnotationsVisitor(IOInfo(), QubitInfo()).visit(parse(code))


def test_raise_on_duplicate_output_index() -> None:
    code = """
    qubit[2] q0;
    qubit[2] q1;

    @leqo.output 0
    let a = q0;
    @leqo.output 0
    let b = q1;
    """
    with pytest.raises(
        IndexError,
        match="Unsupported: duplicate output id: 0",
    ):
        ParseAnnotationsVisitor(IOInfo(), QubitInfo()).visit(parse(code))


def test_raise_on_input_index_not_starting_at_zero() -> None:
    code = """
    @leqo.input 1
    qubit[2] q0;
    @leqo.input 2
    qubit[2] q1;
    """
    with pytest.raises(
        IndexError,
        match="Unsupported: Missing input index 0, next index was 1",
    ):
        ParseAnnotationsVisitor(IOInfo(), QubitInfo()).visit(parse(code))


def test_raise_on_output_index_not_starting_at_zero() -> None:
    code = """
    qubit[2] q0;
    qubit[2] q1;

    @leqo.output 1
    let a = q0;
    @leqo.output 2
    let b = q1;
    """
    with pytest.raises(
        IndexError,
        match="Unsupported: Missing output index 0, next index was 1",
    ):
        ParseAnnotationsVisitor(IOInfo(), QubitInfo()).visit(parse(code))


def test_raise_on_index_on_reusable() -> None:
    code = """
    qubit[2] q1;

    @leqo.reusable 3
    let a = q1;
    """
    with pytest.raises(
        UnsupportedOperation,
        match="Unsupported: found 3 over reusable annotations a",
    ):
        ParseAnnotationsVisitor(IOInfo(), QubitInfo()).visit(parse(code))


def test_raise_on_index_on_dirty() -> None:
    code = """
    @leqo.dirty 3
    qubit[2] q1;
    """
    with pytest.raises(
        UnsupportedOperation,
        match="Unsupported: found 3 over dirty annotations q1",
    ):
        ParseAnnotationsVisitor(IOInfo(), QubitInfo()).visit(parse(code))


def test_raise_on_uncompute_in_uncompute() -> None:
    code = """
    qubit[2] q;

    @leqo.uncompute
    if (false) {
        @leqo.uncompute
        if (false) {
            @leqo.reusable
            let a = q;
        }
    }
    """
    with pytest.raises(
        UnsupportedOperation,
        match="Unsupported: nested uncompute blocks",
    ):
        ParseAnnotationsVisitor(IOInfo(), QubitInfo()).visit(parse(code))


def test_raise_on_invalid_uncompute_expr() -> None:
    code = """
    qubit[2] q;

    @leqo.uncompute
    if (true) {
        @leqo.reusable
        let a = q;
    }
    """
    with pytest.raises(
        UnsupportedOperation,
        match=re.escape(
            "Unsupported: invalid expression in uncompute-annotated if-else-block: BooleanLiteral(span=Span(start_line=5, start_column=8, end_line=5, end_column=8), value=True)",
        ),
    ):
        ParseAnnotationsVisitor(IOInfo(), QubitInfo()).visit(parse(code))


def test_raise_on_output_in_uncompute() -> None:
    code = """
    qubit[2] q;

    @leqo.uncompute
    if (false) {
        @leqo.output 0
        let a = q;
    }
    """
    with pytest.raises(
        UnsupportedOperation,
        match="Unsupported: output declaration over a in uncompute block",
    ):
        ParseAnnotationsVisitor(IOInfo(), QubitInfo()).visit(parse(code))


def test_raise_on_else_in_uncompute() -> None:
    code = """
    qubit[2] q;

    @leqo.uncompute
    if (false) {
        @leqo.reusable
        let a = q;
    } else {
        let a = q;
    }
    """
    with pytest.raises(
        UnsupportedOperation,
        match="Unsupported: uncompute-annotated if-else-block has else-block",
    ):
        ParseAnnotationsVisitor(IOInfo(), QubitInfo()).visit(parse(code))


def test_raise_on_duplicate_declaration_annotation() -> None:
    code = """
    @leqo.input 0
    @leqo.input 1
    qubit[2] q0;
    """
    with pytest.raises(
        UnsupportedOperation,
        match="Unsupported: two input annotations over q0",
    ):
        ParseAnnotationsVisitor(IOInfo(), QubitInfo()).visit(parse(code))


def test_raise_on_duplicate_alias_annotation() -> None:
    code = """
    qubit[2] q0;

    @leqo.output 0
    @leqo.output 1
    let tmp = q0;
    """
    with pytest.raises(
        UnsupportedOperation,
        match="Unsupported: two output annotations over tmp",
    ):
        ParseAnnotationsVisitor(IOInfo(), QubitInfo()).visit(parse(code))


def test_raise_on_input_annotation_over_alias() -> None:
    code = """
    qubit[2] q0;

    @leqo.input 0
    let tmp = q0;
    """
    with pytest.raises(
        UnsupportedOperation,
        match="Unsupported: leqo.input annotations over AliasStatement tmp",
    ):
        ParseAnnotationsVisitor(IOInfo(), QubitInfo()).visit(parse(code))


def test_raise_on_output_annotation_over_declaration() -> None:
    code = """
    @leqo.output 0
    qubit[2] q0;
    """
    with pytest.raises(
        UnsupportedOperation,
        match="Unsupported: leqo.output annotations over QubitDeclaration q0",
    ):
        ParseAnnotationsVisitor(IOInfo(), QubitInfo()).visit(parse(code))


def test_raise_on_reusable_and_output() -> None:
    code = """
    qubit[5] q0;

    @leqo.output 0
    let a = q0[2];
    @leqo.reusable
    let b = q0[2];
    """
    with pytest.raises(
        UnsupportedOperation,
        match="Unsupported: qubit with 2 was parsed as reusable or output twice",
    ):
        ParseAnnotationsVisitor(IOInfo(), QubitInfo()).visit(parse(code))


def test_raise_on_double_output_declaration_on_single_qubit() -> None:
    code = """
    qubit[5] q0;

    @leqo.output 0
    let a = q0[1];
    @leqo.output 1
    let b = q0[1];
    """
    with pytest.raises(
        UnsupportedOperation,
        match="Unsupported: qubit with 1 was parsed as reusable or output twice",
    ):
        ParseAnnotationsVisitor(IOInfo(), QubitInfo()).visit(parse(code))

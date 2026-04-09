import pytest

from app.model.CompileRequest import (
    GateNode,
    MeasurementNode,
    SingleInsert,
    SingleInsertMetaData,
)
from app.transformation_manager import _attach_uncompute_block
from app.transformation_manager.graph import ProgramNode
from app.transformation_manager.pre import preprocess


def test_attach_uncompute_block_adds_inline_block() -> None:
    implementation = """
    OPENQASM 3.1;
    qubit[2] q;
    """

    uncompute = """
    @leqo.reusable
    let _reuse = q;
    """

    result = _attach_uncompute_block(implementation, uncompute)

    assert "@leqo.uncompute" in result
    assert "if(false)" in result
    assert "@leqo.reusable" in result


def test_attach_uncompute_block_is_preprocessable() -> None:
    implementation = """
    OPENQASM 3.1;
    qubit[2] q;
    """

    uncompute = """
    @leqo.reusable
    let _reuse = q;
    """

    code = _attach_uncompute_block(implementation, uncompute)
    processed = preprocess(ProgramNode("n0"), code)

    assert processed is not None


def test_single_insert_accepts_uncompute_implementation() -> None:
    insert = SingleInsert(
        node=GateNode(id="g1", gate="h"),
        implementation="""
        OPENQASM 3.1;
        qubit q;
        h q;
        """,
        uncomputeImplementation="""
        @leqo.reusable
        let _reuse = q;
        """,
        metadata=SingleInsertMetaData(width=1, depth=1),
    )

    assert insert.uncomputeImplementation is not None
    assert "@leqo.reusable" in insert.uncomputeImplementation


def test_single_insert_rejects_uncompute_for_measurement() -> None:
    with pytest.raises(ValueError):
        SingleInsert(
            node=MeasurementNode(id="m1", indices=[0]),
            implementation="""
            OPENQASM 3.1;
            qubit q;
            bit c;
            c = measure q;
            """,
            uncomputeImplementation="""
            @leqo.reusable
            let _reuse = q;
            """,
            metadata=SingleInsertMetaData(width=1, depth=1),

        )

def test_single_insert_rejects_empty_uncompute_implementation() -> None:
    with pytest.raises(ValueError):
        SingleInsert(
            node=GateNode(id="g1", gate="h"),
            implementation="""
            OPENQASM 3.1;
            qubit q;
            h q;
            """,
            uncomputeImplementation="   ",
            metadata=SingleInsertMetaData(width=1, depth=1),
        )      
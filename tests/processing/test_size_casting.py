import re
from io import UnsupportedOperation
from uuid import uuid4

import pytest
from openqasm3.ast import (
    Annotation,
    Concatenation,
    Identifier,
    IntegerLiteral,
    IntType,
    QASMNode,
)

from app.openqasm3.visitor import LeqoTransformer
from app.processing.graph import ProgramNode
from app.processing.pre import preprocess
from app.processing.size_casting import size_cast


class RemoveSpanTransformer(LeqoTransformer[None]):
    def visit_Concatenation(self, node: Concatenation) -> QASMNode:
        node.span = None
        return self.generic_visit(node)

    def visit_Identifier(self, node: Identifier) -> QASMNode:
        node.span = None
        return self.generic_visit(node)

    def visit_IntegerLiteral(self, node: IntegerLiteral) -> QASMNode:
        node.span = None
        return self.generic_visit(node)

    def visit_IntType(self, node: IntType) -> QASMNode:
        node.span = None
        return self.generic_visit(node)

    def visit_Annotation(self, node: Annotation) -> QASMNode:
        node.span = None
        return self.generic_visit(node)


def assert_size_cast(
    before_code: str,
    requested_sizes: dict[int, int],
    expected_code: str,
) -> None:
    dummy_node = ProgramNode("")
    actual = preprocess(dummy_node, before_code)
    size_cast(actual, requested_sizes)
    expected = preprocess(dummy_node, expected_code)
    actual.implementation = RemoveSpanTransformer().visit(actual.implementation)
    expected.implementation = RemoveSpanTransformer().visit(expected.implementation)
    assert actual == expected


def test_qubit_cast() -> None:
    before = """
        OPENQASM 3;
        @leqo.input 0
        qubit[5] q;
        """
    requested_sizes = {0: 2}
    expected = """
        OPENQASM 3;
        @leqo.input 0
        qubit[2] q_0;
        qubit[3] q_1;
        let q = q_0 ++ q_1;
        """
    assert_size_cast(before, requested_sizes, expected)


def test_int_cast() -> None:
    before = """
        OPENQASM 3;
        @leqo.input 0
        int[32] i;
        """
    requested_sizes = {0: 16}
    expected = """
        OPENQASM 3;
        @leqo.input 0
        int[16] i_0;
        int[32] i = i_0;
        """
    assert_size_cast(before, requested_sizes, expected)


def test_float_cast() -> None:
    before = """
        OPENQASM 3;
        @leqo.input 0
        float[32] i;
        """
    requested_sizes = {0: 16}
    expected = """
        OPENQASM 3;
        @leqo.input 0
        float[16] i_0;
        float[32] i = i_0;
        """
    assert_size_cast(before, requested_sizes, expected)


def test_bit_cast() -> None:
    before = """
        OPENQASM 3;
        @leqo.input 0
        bit[32] b;
        """
    requested_sizes = {0: 16}
    expected = """
        OPENQASM 3;
        @leqo.input 0
        bit[16] b_0;
        bit[16] b_1;
        let b = b_0 ++ b_1;
        """
    assert_size_cast(before, requested_sizes, expected)


def test_cast_qubit_and_classic() -> None:
    before = """
        OPENQASM 3;
        @leqo.input 0
        qubit[5] q;
        @leqo.input 1
        int[32] i;
        """
    requested_sizes = {0: 2, 1: 16}
    expected = """
        OPENQASM 3;
        @leqo.input 0
        qubit[2] q_0;
        qubit[3] q_1;
        let q = q_0 ++ q_1;
        @leqo.input 1
        int[16] i_0;
        int[32] i = i_0;
        """
    assert_size_cast(before, requested_sizes, expected)


def test_trivial_non_cast() -> None:
    before = """
        OPENQASM 3;
        @leqo.input 0
        qubit[5] q;
        @leqo.input 1
        int[32] i;
        """
    requested_sizes = {0: 5, 1: 32}
    expected = """
        OPENQASM 3;
        @leqo.input 0
        qubit[5] q;
        @leqo.input 1
        int[32] i;
        """
    assert_size_cast(before, requested_sizes, expected)


def test_raise_on_invalid_qubit_cast() -> None:
    before = """
        OPENQASM 3;
        @leqo.input 0
        qubit[5] q;
        """
    requested_sizes = {0: 10000}

    id = uuid4()
    with pytest.raises(
        UnsupportedOperation,
        match=re.escape(
            f"Try to make QubitIOInstance(name='leqo_{id.hex}_q', ids=[0, 1, 2, 3, 4]) bigger, only smaller is possible.",
        ),
    ):
        size_cast(preprocess(ProgramNode("", id=id), before), requested_sizes)


def test_raise_on_invalid_classic_cast() -> None:
    before = """
        OPENQASM 3;
        @leqo.input 0
        int[5] i;
        """
    requested_sizes = {0: 10000}

    id = uuid4()
    with pytest.raises(
        UnsupportedOperation,
        match=re.escape(
            f"Try to make ClassicalIOInstance(name='leqo_{id.hex}_i', type=IntType(bit_size=5)) bigger, only smaller is possible.",
        ),
    ):
        size_cast(preprocess(ProgramNode("", id=id), before), requested_sizes)

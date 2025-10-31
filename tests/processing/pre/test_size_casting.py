import re
from uuid import uuid4

import pytest

from app.openqasm3.printer import leqo_dumps
from app.transformation_manager.graph import ProgramNode
from app.transformation_manager.pre import preprocess
from app.transformation_manager.pre.size_casting import size_cast
from app.transformation_manager.pre.utils import PreprocessingException
from app.transformation_manager.utils import normalize_qasm_string


def assert_size_cast(
    before_code: str,
    requested_sizes: dict[int, int | None],
    expected_code: str,
) -> None:
    dummy_node = ProgramNode("")
    actual = preprocess(dummy_node, before_code)
    size_cast(actual, requested_sizes)
    expected = preprocess(dummy_node, expected_code)
    assert normalize_qasm_string(
        leqo_dumps(actual.implementation)
    ) == normalize_qasm_string(leqo_dumps(expected.implementation))


def test_qubit_cast() -> None:
    before = """
        OPENQASM 3;
        @leqo.input 0
        qubit[5] q;
        """
    expected = """
        OPENQASM 3;
        @leqo.input 0
        qubit[2] q_0;
        qubit[3] q_1;
        let q = q_0 ++ q_1;
        """
    assert_size_cast(before, {0: 2}, expected)


def test_int_cast() -> None:
    before = """
        OPENQASM 3;
        @leqo.input 0
        int[32] i;
        """
    expected = """
        OPENQASM 3;
        @leqo.input 0
        int[16] i_0;
        int[32] i = i_0;
        """
    assert_size_cast(before, {0: 16}, expected)


def test_float_cast() -> None:
    before = """
        OPENQASM 3;
        @leqo.input 0
        float[32] i;
        """
    expected = """
        OPENQASM 3;
        @leqo.input 0
        float[16] i_0;
        float[32] i = i_0;
        """
    assert_size_cast(before, {0: 16}, expected)


def test_bit_cast() -> None:
    before = """
        OPENQASM 3;
        @leqo.input 0
        bit[32] b;
        """
    expected = """
        OPENQASM 3;
        @leqo.input 0
        bit[16] b_0;
        bit[16] b_1;
        let b = b_0 ++ b_1;
        """
    assert_size_cast(before, {0: 16}, expected)


def test_bit_array_to_bit_cast() -> None:
    before = """
        OPENQASM 3;
        @leqo.input 0
        bit[32] b;
        """
    expected = """
        OPENQASM 3;
        @leqo.input 0
        bit b_0;
        bit[1] b_1 = b_0;
        bit[31] b_2;
        let b = b_1 ++ b_2;
        """
    assert_size_cast(before, {0: None}, expected)


def test_cast_qubit_and_classic() -> None:
    before = """
        OPENQASM 3;
        @leqo.input 0
        qubit[5] q;
        @leqo.input 1
        int[32] i;
        """
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
    assert_size_cast(before, {0: 2, 1: 16}, expected)


def test_trivial_non_cast() -> None:
    before = """
        OPENQASM 3;
        @leqo.input 0
        qubit[5] q;
        @leqo.input 1
        int[32] i;
        """
    expected = """
        OPENQASM 3;
        @leqo.input 0
        qubit[5] q;
        @leqo.input 1
        int[32] i;
        """
    assert_size_cast(before, {0: 5, 1: 32}, expected)


def test_raise_on_invalid_qubit_cast() -> None:
    before = """
        OPENQASM 3;
        @leqo.input 0
        qubit[5] q;
        """

    id = uuid4()
    with pytest.raises(
        PreprocessingException,
        match=(
            re.escape(
                f"Try to make QubitIOInstance(name='leqo_{id.hex}_q', ids=[0, 1, 2, 3, 4]"
            )
            + r"(, signed=(True|False))?\) bigger, only smaller is possible\."
        ),
    ):
        size_cast(preprocess(ProgramNode("", id=id), before), {0: 10000})


def test_raise_on_invalid_classic_cast() -> None:
    before = """
        OPENQASM 3;
        @leqo.input 0
        int[5] i;
        """

    id = uuid4()
    with pytest.raises(
        PreprocessingException,
        match=re.escape(
            f"Try to make ClassicalIOInstance(name='leqo_{id.hex}_i', type=IntType(size=5)) bigger, only smaller is possible.",
        ),
    ):
        size_cast(preprocess(ProgramNode("", id=id), before), {0: 10000})

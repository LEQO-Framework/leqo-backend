from io import UnsupportedOperation

import pytest
from openqasm3.ast import Annotation, IndexedIdentifier, QuantumGate
from openqasm3.parser import parse

from app.processing.utils import parse_io_annotation, parse_qasm_index


def test_parse_io_annotation() -> None:
    def assert_parse(command: str | None, expected: int) -> None:
        assert parse_io_annotation(Annotation("leqo.input", command)) == expected, (
            f"'{command}' != {expected}"
        )
        assert parse_io_annotation(Annotation("leqo.output", command)) == expected, (
            f"'{command}' != {expected}"
        )

    def assert_parse_failure(command: str | None, match: str) -> None:
        with pytest.raises(UnsupportedOperation, match=match):
            parse_io_annotation(Annotation("leqo.input", command))

        with pytest.raises(UnsupportedOperation, match=match):
            parse_io_annotation(Annotation("leqo.output", command))

    assert_parse("1", 1)
    assert_parse(" 3   ", 3)
    assert_parse("5", 5)
    assert_parse_failure(
        "",
        "Annotation of type Annotation without index was found.",
    )
    assert_parse_failure(
        "      ",
        "Annotation of type Annotation without index was found.",
    )


def test_parse_qasm_index() -> None:
    def assert_parse(index_str: str, length: int, expected: list[int]) -> None:
        ast = parse(f"x q{index_str};")
        statement = ast.statements[0]
        if not isinstance(statement, QuantumGate):
            msg = "This should not be possible..."
            raise TypeError(msg)
        qubit = statement.qubits[0]
        if not isinstance(qubit, IndexedIdentifier):
            msg = "This should not be possible..."
            raise TypeError(msg)
        result = parse_qasm_index(qubit.indices, length)
        assert result == expected

    assert_parse("[0]", 1, [0])
    assert_parse("[3]", 5, [3])
    assert_parse("[0:3]", 4, [0, 1, 2, 3])
    assert_parse("[0:2]", 4, [0, 1, 2])
    assert_parse("[1:2]", 4, [1, 2])
    assert_parse("[0:-1]", 3, [0, 1, 2])
    assert_parse("[1:-1]", 3, [1, 2])
    assert_parse("[1:-2]", 5, [1, 2, 3])
    assert_parse("[1:-4]", 5, [1])
    assert_parse("[0:2:5]", 10, [0, 2, 4])
    assert_parse("[0:3:9]", 10, [0, 3, 6, 9])
    assert_parse("[3:-1:1]", 10, [3, 2, 1])
    assert_parse("[8:-2:0]", 10, [8, 6, 4, 2, 0])
    assert_parse("[1:]", 3, [1, 2])
    assert_parse("[:1]", 3, [0, 1])
    assert_parse("[:]", 3, [0, 1, 2])
    assert_parse("[{1, 2, 4}]", 10000, [1, 2, 4])
    assert_parse("[{0, 1, 2, 3}][0:2][0]", 4, [0])
    assert_parse("[{3, 2, 1, 0}][1:3][0:1]", 4, [2, 1])
    with pytest.raises(IndexError):
        assert_parse("[1000]", 4, [])
    with pytest.raises(IndexError):
        assert_parse("[0:1000]", 4, [])
    with pytest.raises(IndexError):
        assert_parse("[{3, 2}][3]", 4, [])

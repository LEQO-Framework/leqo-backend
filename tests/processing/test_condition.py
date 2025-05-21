import pytest
from openqasm3.ast import (
    IntegerLiteral,
)

from app.openqasm3.printer import leqo_dumps
from app.processing.condition import _ParserList, parse_condition, tokenize


def assert_tokenizer(input: str, result: list[str]) -> None:
    assert list(tokenize(_ParserList(input))) == result


def test_tokenize():
    assert_tokenizer(
        " [ 0, 1,2,3]==]!=[&&]|| ",
        [
            "[",
            IntegerLiteral(0),
            ",",
            IntegerLiteral(1),
            ",",
            IntegerLiteral(2),
            ",",
            IntegerLiteral(3),
            "]",
            "==",
            "]",
            "!=",
            "[",
            "&&",
            "]",
            "||",
        ],
    )


def assert_parse(input: str, result: str) -> None:
    assert leqo_dumps(parse_condition(input)) == result


def test_parse_bitstring():
    # assert_parse("abc==[]", 'abc == ""')
    # assert_parse(" abc == [ ] ", 'abc == ""')
    assert_parse(" a == [0] ", 'a == "0"')
    assert_parse(" a == [0,1, 0,1] ", 'a == "0101"')


def test_parse_complex():
    assert_parse(
        "a == [0,1 ,0] || c == d && (i != j || ab == !c) && !(!a == b)",
        'a == "010" || c == d && (i != j || ab == !c) && !(!a == b)',
    )


def test_eof():
    with pytest.raises(Exception, match="^unexpected token None$"):
        parse_condition("")
    with pytest.raises(
        Exception,
        match="^expected \\[None\\] but got Identifier\\(span=None, name='a'\\)$",
    ):
        parse_condition("a a")
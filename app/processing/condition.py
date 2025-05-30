from collections.abc import Iterable
from typing import Generic, TypeVar

from openqasm3.ast import (
    BinaryExpression,
    BinaryOperator,
    BitstringLiteral,
    Expression,
    Identifier,
    IntegerLiteral,
    UnaryExpression,
    UnaryOperator,
)

T = TypeVar("T")


class _ParserList(Generic[T]):
    _items: list[T]
    _index: int

    def __init__(self, items: list[T] | Iterable[T]):
        self._items = list(items)
        self._index = 0

    def peek(self, offset=0) -> T | None:
        if offset < 0 or (self._index + offset) >= len(self._items):
            return None

        return self._items[self._index + offset]

    def read(self) -> T | None:
        result = self.peek()
        if result is None:
            return None

        self._index += 1
        return result

    def match(self, *expected: T | None) -> T | None:
        actual = self.read()
        if actual not in expected:
            raise Exception(f"expected {list(expected)} but got {actual}")
        return actual


def _read_number(input: _ParserList[str], first: str) -> IntegerLiteral:
    result = first
    while True:
        ch = input.peek()
        if ch is None or not ch.isnumeric():
            break

        result += ch
        input.read()
    return IntegerLiteral(int(result))


def _read_identifier(input: _ParserList[str], first: str) -> Identifier:
    result = first
    while True:
        ch = input.peek()
        if ch is None or not ch.isalpha():
            break

        result += ch
        input.read()
    return Identifier(result)


_ConditionToken = str | IntegerLiteral | Identifier


def tokenize(input: _ParserList[str]) -> Iterable[_ConditionToken]:
    while True:
        ch = input.read()
        match ch:
            case None:
                break
            case " ":
                continue
            case "[" | "]" | "(" | ")" | ",":
                yield ch
            case "=":
                input.match("=")
                yield "=="
            case "!":
                if input.peek() != "=":
                    yield "!"
                else:
                    input.match("=")
                    yield "!="
            case "&":
                input.match("&")
                yield "&&"
            case "|":
                input.match("|")
                yield "||"
            case _ if ch.isnumeric():
                yield _read_number(input, ch)
            case _ if ch.isalpha():
                yield _read_identifier(input, ch)
            case _:
                raise Exception(f"unexpected token {ch!r}")


class Parser:
    tokens: _ParserList[_ConditionToken]

    def __init__(self, tokens: _ParserList[_ConditionToken]):
        self.tokens = tokens

    def _bitstring(self) -> BitstringLiteral:
        self.tokens.match("[")

        width = 0
        value = 0
        while True:
            token = self.tokens.read()
            if token == "]":
                break
            if not isinstance(token, IntegerLiteral):
                raise Exception(f"unexpected token {token!r}")
            if token.value not in (0, 1):
                raise Exception(f"unexpected token {token!r}")

            value += pow(2, width) * token.value
            width += 1

            if self.tokens.match(",", "]") == "]":
                break

        return BitstringLiteral(value, width)

    def _identifier(self) -> Identifier:
        token = self.tokens.read()
        if not isinstance(token, Identifier):
            raise Exception(f"unexpected token {token!r}")
        return token

    def _atom(
        self,
    ) -> Expression:
        token = self.tokens.peek()
        match token:
            case Identifier():
                self.tokens.match(token)
                return token
            case "[":
                return self._bitstring()
            case "(":
                self.tokens.match("(")
                result = self._or_chain()
                self.tokens.match(")")
                return result
            case "!":
                self.tokens.match("!")
                return UnaryExpression(UnaryOperator["!"], self._atom())
            case _:
                raise Exception(f"unexpected token {token!r}")

    def _comparison_or_atom(self) -> Expression:
        lhs = self._atom()
        if self.tokens.peek() not in ["==", "!="]:
            return lhs

        op = self.tokens.read()
        rhs = self._atom()
        match op:
            case "==":
                return BinaryExpression(BinaryOperator["=="], lhs, rhs)
            case "!=":
                return BinaryExpression(BinaryOperator["!="], lhs, rhs)
            case _:
                raise Exception(f"unexpected operator {op!r}")

    def _and_chain(self) -> Expression:
        result: Expression = self._comparison_or_atom()
        while self.tokens.peek() == "&&":
            self.tokens.match("&&")
            result = BinaryExpression(
                BinaryOperator["&&"], result, self._comparison_or_atom()
            )
        return result

    def _or_chain(self) -> Expression:
        result: Expression = self._and_chain()
        while self.tokens.peek() == "||":
            self.tokens.match("||")
            result = BinaryExpression(BinaryOperator["||"], result, self._and_chain())
        return result

    def parse(self) -> Expression:
        result = self._or_chain()
        self.tokens.match(None)
        return result


def parse_condition(value: str) -> Expression:
    tokens = _ParserList(tokenize(_ParserList(value)))
    
    parser = Parser(tokens)
    return parser.parse()

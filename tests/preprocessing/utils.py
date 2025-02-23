from textwrap import dedent

from openqasm3.parser import parse
from openqasm3.printer import dumps
from openqasm3.visitor import QASMTransformer


def assert_processor(
    transformer: QASMTransformer[None], original: str, expected: str
) -> None:
    assert dumps(transformer.visit(parse(original))) == dedent(expected)

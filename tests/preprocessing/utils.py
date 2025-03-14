from textwrap import dedent

from openqasm3.parser import parse
from openqasm3.printer import dumps
from openqasm3.visitor import QASMTransformer

from app.model.SectionInfo import SectionInfo


def assert_processor(
    transformer: QASMTransformer[SectionInfo],
    section_info: SectionInfo,
    original: str,
    expected: str,
) -> None:
    assert dumps(transformer.visit(parse(original), section_info)) == dedent(expected)

from textwrap import dedent

from openqasm3.parser import parse
from openqasm3.printer import dumps
from openqasm3.visitor import QASMTransformer

from app.processing.graph import SectionInfo


def assert_processor(
    transformer: QASMTransformer[SectionInfo],
    section_info: SectionInfo,
    original: str,
    expected: str,
) -> None:
    program = parse(original)
    program = transformer.visit(program, section_info)
    processed = dumps(program)
    assert processed == dedent(expected), f"{processed} != {expected}"

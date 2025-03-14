from openqasm3.parser import parse

from app.model.SectionInfo import SectionInfo
from app.preprocessing.memory import MemoryTransformer


def test_extract_memory_info() -> None:
    original = """
    OPENQASM 3.0;
    include "stdgates.inc";
    
    @leqo.input 1
    qubit someInput;
    
    @leqo.output 1
    qubit someOutput;
    
    @leqo.input 2
    @leqo.output 3
    qubit someRef;
    """

    section_info = SectionInfo(1, globals={})
    MemoryTransformer().visit(parse(original), section_info)

    assert section_info.globals["someInput"].inputIndex == 1
    assert section_info.globals["someInput"].outputIndex is None

    assert section_info.globals["someOutput"].inputIndex is None
    assert section_info.globals["someOutput"].outputIndex == 1

    assert section_info.globals["someRef"].inputIndex == 2
    assert section_info.globals["someRef"].outputIndex == 3

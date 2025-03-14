from openqasm3.parser import parse

from app.model.SectionInfo import SectionInfo
from app.preprocessing import MemoryTransformer


def test_extract_memory_info():
    original = """
    OPENQASM 3.0;
    include "stdgates.inc";
    
    @leqo.input
    qubit someInput;
    
    @leqo.output
    qubit someOutput;
    
    @leqo.input
    @leqo.output
    qubit someRef;
    
    h someInput;
    reset someInput;
    h someInput;
    
    reset someRef;
    
    h someOutput;
    """

    section_info = SectionInfo(1, globals={})
    MemoryTransformer().visit(parse(original), section_info)

    assert not section_info.globals["someInput"].isReset
    assert section_info.globals["someInput"].isInput
    assert not section_info.globals["someInput"].isOutput

    assert not section_info.globals["someOutput"].isReset
    assert not section_info.globals["someOutput"].isInput
    assert section_info.globals["someOutput"].isOutput

    assert section_info.globals["someRef"].isReset
    assert section_info.globals["someRef"].isInput
    assert section_info.globals["someRef"].isOutput

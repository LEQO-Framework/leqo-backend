from uuid import uuid4

from app.processing.graph import SectionInfo
from app.processing.pre.inlining import InliningTransformer
from tests.processing.utils import assert_processor


def test_inline_aliases() -> None:
    section_info = SectionInfo(uuid4())
    assert_processor(
        InliningTransformer(),
        section_info,
        """
        OPENQASM 3;
        qubit q;
        qubit q2;
        
        const int[8] c0 = 0;
        const int[16] c1 = -1;
        const float[32] c2 = 0.1;
        const uint[32] c3 = 42;
        const bit c4 = measure q2;
        
        x q[c0];
        x q[c1];
        x q[c2];
        x q[c3];
        x q[c4];
        """,
        """\
        OPENQASM 3;
        qubit q;
        qubit q2;
        const int[16] c1 = -1;
        const float[32] c2 = 0.1;
        const bit c4 = measure q2;
        x q[0];
        x q[c1];
        x q[c2];
        x q[42];
        x q[c4];
        """,
    )

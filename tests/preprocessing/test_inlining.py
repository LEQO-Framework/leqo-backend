from app.model.SectionInfo import SectionInfo
from app.preprocessing.inlining import InliningTransformer
from tests.preprocessing.utils import assert_processor


def test_inline_aliases() -> None:
    section_info = SectionInfo(1, globals={})
    assert_processor(
        InliningTransformer(),
        section_info,
        """
        OPENQASM 3;
        include "stdgates.inc";
        bit[2] c;
        const int n = 42;
        qubit[4] _all_qubits;
        let q = _all_qubits[0:3];
        x q[0];
        let test = n;
        """,
        """\
        OPENQASM 3;
        include "stdgates.inc";
        bit[2] c;
        qubit[4] _all_qubits;
        let q = _all_qubits[0:3];
        x q[0];
        let test = 42;
        """,
    )

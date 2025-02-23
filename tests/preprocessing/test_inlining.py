from app.preprocessing.inlining import InliningTransformer
from tests.preprocessing.utils import assert_processor


def test_inline_aliases() -> None:
    assert_processor(
        InliningTransformer(),
        """
        OPENQASM 3;
        include "stdgates.inc";
        bit[2] c;
        qubit[4] _all_qubits;
        let q = _all_qubits[0:3];
        x q[0];
        x q[1];
        cx q[0], q[2];
        cx q[1], q[2];
        ccx q[0], q[1], q[3];
        """,
        """\
        OPENQASM 3;
        include "stdgates.inc";
        bit[2] c;
        qubit[4] _all_qubits;
        x _all_qubits[0:3][0];
        x _all_qubits[0:3][1];
        cx _all_qubits[0:3][0], _all_qubits[0:3][2];
        cx _all_qubits[0:3][1], _all_qubits[0:3][2];
        ccx _all_qubits[0:3][0], _all_qubits[0:3][1], _all_qubits[0:3][3];
        """,
    )

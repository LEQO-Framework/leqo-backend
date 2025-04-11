from openqasm3.parser import parse

from app.processing.io_info import (
    CombinedIOInfo,
    QubitAnnotationInfo,
    QubitIOInfo,
    RegSingleInputInfo,
    RegSingleOutputInfo,
)
from app.processing.pre.io_parser import ParseAnnotationsVisitor
from app.processing.utils import normalize_qasm_string


def test_all() -> None:
    code = normalize_qasm_string("""
    @leqo.input 0
    qubit[5] q0;
    @leqo.input 1
    qubit[5] q1;
    @leqo.dirty
    qubit q2;

    let a = q1[{4, 3, 2, 1, 0}];

    @leqo.output 0
    let _out0 = q0[0] ++ q1[0];
    @leqo.output 1
    let _out1 = q0[1] ++ a[1]; // a[1] == q1[3]

    @leqo.reusable
    let _reuse = q0[2:4];
    """)
    expected = CombinedIOInfo(
        qubit=QubitIOInfo(
            declaration_to_ids={
                "q0": [0, 1, 2, 3, 4],
                "q1": [5, 6, 7, 8, 9],
                "q2": [10],
            },
            id_to_info={
                0: QubitAnnotationInfo(
                    input=RegSingleInputInfo(0, 0),
                    output=RegSingleOutputInfo(0, 0),
                ),
                1: QubitAnnotationInfo(
                    input=RegSingleInputInfo(0, 1),
                    output=RegSingleOutputInfo(1, 0),
                ),
                2: QubitAnnotationInfo(input=RegSingleInputInfo(0, 2), reusable=True),
                3: QubitAnnotationInfo(input=RegSingleInputInfo(0, 3), reusable=True),
                4: QubitAnnotationInfo(input=RegSingleInputInfo(0, 4), reusable=True),
                5: QubitAnnotationInfo(
                    input=RegSingleInputInfo(1, 0),
                    output=RegSingleOutputInfo(0, 1),
                ),
                6: QubitAnnotationInfo(input=RegSingleInputInfo(1, 1)),
                7: QubitAnnotationInfo(input=RegSingleInputInfo(1, 2)),
                8: QubitAnnotationInfo(
                    input=RegSingleInputInfo(1, 3),
                    output=RegSingleOutputInfo(1, 1),
                ),
                9: QubitAnnotationInfo(input=RegSingleInputInfo(1, 4)),
                10: QubitAnnotationInfo(dirty=True),
            },
            input_to_ids={0: [0, 1, 2, 3, 4], 1: [5, 6, 7, 8, 9]},
            output_to_ids={0: [0, 5], 1: [1, 8]},
            dirty_ancillas=[10],
            reusable_ancillas=[2, 3, 4],
            returned_dirty_ancillas=[6, 7, 9, 10],
        ),
    )
    actual = CombinedIOInfo()
    ParseAnnotationsVisitor(actual).visit(parse(code))
    assert expected == actual

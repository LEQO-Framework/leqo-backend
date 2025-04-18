from textwrap import dedent
from uuid import uuid4

from openqasm3.parser import parse
from openqasm3.printer import dumps

from app.processing.pre.renaming import RenameRegisterTransformer


def test_register_renaming() -> None:
    id = uuid4()
    original = f"""
        OPENQASM 3;
        @leqo.input 0
        float f1;
        @leqo.input 1
        float f2;
        @leqo.input 2
        qubit q1;
        @leqo.input 3
        qubit[1] q1_2;
        @leqo.input 4
        qubit[2] q2;
        @leqo.input 5
        qubit[3] q3;
        @leqo.input 6
        qubit leqo_{id.hex}_f1;
        @leqo.input 7
        let alias = q1_2;
        @leqo.input 8
        bit classicalTest = q1_2;
        @leqo.input 9
        const bit classicalTest2 = measure q1_2;
        x q1;
        x q1_2;
        x q2;
        x q3;
        x leqo_{id.hex}_f1;
        """
    expected = f"""\
        OPENQASM 3;
        @leqo.input 0
        float leqo_{id.hex}_f1;
        @leqo.input 1
        float leqo_{id.hex}_f2;
        @leqo.input 2
        qubit leqo_{id.hex}_q1;
        @leqo.input 3
        qubit[1] leqo_{id.hex}_q1_2;
        @leqo.input 4
        qubit[2] leqo_{id.hex}_q2;
        @leqo.input 5
        qubit[3] leqo_{id.hex}_q3;
        @leqo.input 6
        qubit leqo_{id.hex}_leqo_{id.hex}_f1;
        @leqo.input 7
        let leqo_{id.hex}_alias = leqo_{id.hex}_q1_2;
        @leqo.input 8
        bit leqo_{id.hex}_classicalTest = leqo_{id.hex}_q1_2;
        @leqo.input 9
        const bit leqo_{id.hex}_classicalTest2 = measure leqo_{id.hex}_q1_2;
        x leqo_{id.hex}_q1;
        x leqo_{id.hex}_q1_2;
        x leqo_{id.hex}_q2;
        x leqo_{id.hex}_q3;
        x leqo_{id.hex}_leqo_{id.hex}_f1;
        """
    program = parse(original)
    program = RenameRegisterTransformer().visit(program, id)
    processed = dumps(program)
    assert processed == dedent(expected), f"{processed} != {expected}"

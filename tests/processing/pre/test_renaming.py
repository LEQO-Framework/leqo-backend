from uuid import uuid4

from app.processing.graph import SectionInfo
from app.processing.pre.renaming import RenameRegisterTransformer
from tests.processing.utils import assert_processor


def test_register_renaming() -> None:
    id = uuid4()
    section_info = SectionInfo(id)
    assert_processor(
        RenameRegisterTransformer(),
        section_info,
        f"""
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
        qubit leqo_{id.hex}_declaration1;
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
        x leqo_{id.hex}_declaration1;
        """,
        f"""\
        OPENQASM 3;
        @leqo.input 0
        float leqo_{id.hex}_declaration0;
        @leqo.input 1
        float leqo_{id.hex}_declaration1;
        @leqo.input 2
        qubit leqo_{id.hex}_declaration2;
        @leqo.input 3
        qubit[1] leqo_{id.hex}_declaration3;
        @leqo.input 4
        qubit[2] leqo_{id.hex}_declaration4;
        @leqo.input 5
        qubit[3] leqo_{id.hex}_declaration5;
        @leqo.input 6
        qubit leqo_{id.hex}_declaration6;
        @leqo.input 7
        let leqo_{id.hex}_declaration7 = leqo_{id.hex}_declaration3;
        @leqo.input 8
        bit leqo_{id.hex}_declaration8 = leqo_{id.hex}_declaration3;
        @leqo.input 9
        const bit leqo_{id.hex}_declaration9 = measure leqo_{id.hex}_declaration3;
        x leqo_{id.hex}_declaration2;
        x leqo_{id.hex}_declaration3;
        x leqo_{id.hex}_declaration4;
        x leqo_{id.hex}_declaration5;
        x leqo_{id.hex}_declaration6;
        """,
    )

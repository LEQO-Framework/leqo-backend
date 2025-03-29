from app.processing.graph import ProgramNode, QasmImplementation, SectionInfo
from app.processing.pre.renaming import RenameRegisterTransformer
from tests.processing.utils import assert_processor


def test_register_renaming() -> None:
    section_info = SectionInfo(
        1, node=ProgramNode("42", QasmImplementation.create("qubit a;"), None)
    )
    assert_processor(
        RenameRegisterTransformer(),
        section_info,
        """
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
        qubit leqo_section1_declaration1;
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
        x leqo_section1_declaration1;
        """,
        """\
        OPENQASM 3;
        @leqo.input 0
        float leqo_section1_declaration0;
        @leqo.input 1
        float leqo_section1_declaration1;
        @leqo.input 2
        qubit leqo_section1_declaration2;
        @leqo.input 3
        qubit[1] leqo_section1_declaration3;
        @leqo.input 4
        qubit[2] leqo_section1_declaration4;
        @leqo.input 5
        qubit[3] leqo_section1_declaration5;
        @leqo.input 6
        qubit leqo_section1_declaration6;
        @leqo.input 7
        let leqo_section1_declaration7 = leqo_section1_declaration3;
        @leqo.input 8
        bit leqo_section1_declaration8 = leqo_section1_declaration3;
        @leqo.input 9
        const bit leqo_section1_declaration9 = measure leqo_section1_declaration3;
        x leqo_section1_declaration2;
        x leqo_section1_declaration3;
        x leqo_section1_declaration4;
        x leqo_section1_declaration5;
        x leqo_section1_declaration6;
        """,
    )

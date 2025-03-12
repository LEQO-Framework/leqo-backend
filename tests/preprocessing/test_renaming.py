from app.preprocessing.renaming import RenameRegisterTransformer
from tests.preprocessing.utils import assert_processor


def test_register_renaming() -> None:
    assert_processor(
        RenameRegisterTransformer(),
        """
        OPENQASM 3;
        float f1;
        float f2;
        qubit q1;
        qubit[1] q1_2;
        qubit[2] q2;
        qubit[3] q3;
        qubit leqo_section1_declaration1;
        x q1;
        x q1_2;
        x q2;
        x q3;
        x leqo_section1_declaration1;
        """,
        """\
        OPENQASM 3;
        float leqo_section1_declaration0;
        float leqo_section1_declaration1;
        qubit leqo_section1_declaration2;
        qubit[1] leqo_section1_declaration3;
        qubit[2] leqo_section1_declaration4;
        qubit[3] leqo_section1_declaration5;
        qubit leqo_section1_declaration6;
        x leqo_section1_declaration2;
        x leqo_section1_declaration3;
        x leqo_section1_declaration4;
        x leqo_section1_declaration5;
        x leqo_section1_declaration6;
        """,
    )

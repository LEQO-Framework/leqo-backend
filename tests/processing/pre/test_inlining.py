from textwrap import dedent

from openqasm3.parser import parse
from openqasm3.printer import dumps

from app.transformation_manager.pre.inlining import InliningTransformer


def test_inline_aliases() -> None:
    original = """
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
        """
    expected = """\
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
        """
    program = parse(original)
    program = InliningTransformer().visit(program)
    processed = dumps(program)
    assert processed == dedent(expected), f"{processed} != {expected}"

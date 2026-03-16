import openqasm3.ast as qast
from app.openqasm3.universal_transpiler import UniversalTranspiler
from app.openqasm3.braket_provider import BraketProvider

def test_braket_basic_gates():
    provider = BraketProvider()
    transpiler = UniversalTranspiler(provider)
    
    # Create a simple OpenQASM 3 program AST manually
    # qubit q;
    # h q;
    # x q;
    program = qast.Program(
        statements=[
            qast.QubitDeclaration(qubit=qast.Identifier(name="q"), size=None),
            qast.QuantumGate(name=qast.Identifier(name="h"), arguments=[], qubits=[qast.Identifier(name="q")], modifiers=[]),
            qast.QuantumGate(name=qast.Identifier(name="x"), arguments=[], qubits=[qast.Identifier(name="q")], modifiers=[])
        ],
        version="3.0"
    )
    
    python_code = transpiler.visit_Program(program)
    print("\nGenerated Braket Code:")
    print(python_code)
    
    assert "from braket.circuits import Circuit" in python_code
    assert "c = Circuit()" in python_code
    assert "c.h(0)" in python_code
    assert "c.x(0)" in python_code

if __name__ == "__main__":
    test_braket_basic_gates()

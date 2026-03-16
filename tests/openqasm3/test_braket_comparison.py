import openqasm3.ast as qast
from app.openqasm3.universal_transpiler import UniversalTranspiler
from app.openqasm3.braket_provider import BraketProvider
from app.openqasm3.qiskit_provider import QiskitProvider

def test_generate_comparison():
    # Manual OpenQASM 3 AST for a Parameterized GHZ-like state
    program = qast.Program(
        statements=[
            qast.IODeclaration(
                io_identifier=qast.Identifier(name="input"),
                type=qast.FloatType(size=None),
                identifier=qast.Identifier(name="theta")
            ),
            qast.QubitDeclaration(qubit=qast.Identifier(name="q"), size=qast.IntegerLiteral(value=3)),
            qast.QuantumGate(name=qast.Identifier(name="h"), arguments=[], 
                             qubits=[qast.IndexedIdentifier(name=qast.Identifier(name="q"), indices=[[qast.IntegerLiteral(value=0)]])], modifiers=[]),
            qast.QuantumGate(name=qast.Identifier(name="rx"), arguments=[qast.Identifier(name="theta")], 
                             qubits=[qast.IndexedIdentifier(name=qast.Identifier(name="q"), indices=[[qast.IntegerLiteral(value=0)]])], modifiers=[]),
            qast.QuantumGate(name=qast.Identifier(name="cnot"), arguments=[], 
                             qubits=[
                                 qast.IndexedIdentifier(name=qast.Identifier(name="q"), indices=[[qast.IntegerLiteral(value=0)]]),
                                 qast.IndexedIdentifier(name=qast.Identifier(name="q"), indices=[[qast.IntegerLiteral(value=1)]])
                             ], modifiers=[]),
            qast.QuantumGate(name=qast.Identifier(name="cnot"), arguments=[], 
                             qubits=[
                                 qast.IndexedIdentifier(name=qast.Identifier(name="q"), indices=[[qast.IntegerLiteral(value=1)]]),
                                 qast.IndexedIdentifier(name=qast.Identifier(name="q"), indices=[[qast.IntegerLiteral(value=2)]])
                             ], modifiers=[]),
            qast.QuantumMeasurementStatement(
                measure=qast.QuantumMeasurement(qubit=qast.Identifier(name="q")),
                target=None
            )
        ],
        version="3.0"
    )

    # Generate Qiskit
    qiskit_code = UniversalTranspiler(QiskitProvider()).visit_Program(program)
    
    # Generate Braket
    braket_code = UniversalTranspiler(BraketProvider()).visit_Program(program)

    print("-" * 20 + " QISKIT GENERATED " + "-" * 20)
    print(qiskit_code)
    print("\n" + "-" * 20 + " BRAKET GENERATED " + "-" * 20)
    print(braket_code)

if __name__ == "__main__":
    test_generate_comparison()

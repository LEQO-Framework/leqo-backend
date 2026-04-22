import math

from qiskit import QuantumCircuit
from qiskit.circuit.library import PhaseGate
from qiskit.quantum_info import Statevector


def controlled_power(base_gate, power: int):
    return base_gate.power(power).control(1)


def build_iqft_2(qc: QuantumCircuit, wires: list[int]) -> None:
   
    qc.swap(wires[0], wires[1])
    qc.h(wires[1])
    qc.cp(-math.pi / 2, wires[1], wires[0])
    qc.h(wires[0])


def build_toy_qpe() -> QuantumCircuit:
    qc = QuantumCircuit(3)

    estimation_wires = [0, 1]
    target_wire = 2

   
    qc.x(target_wire)

    
    for wire in estimation_wires:
        qc.h(wire)

  
    base_gate = PhaseGate(2 * math.pi * 0.25)

   
    qc.append(controlled_power(base_gate, 2), [estimation_wires[0], target_wire])
    qc.append(controlled_power(base_gate, 1), [estimation_wires[1], target_wire])

  
    build_iqft_2(qc, estimation_wires)

    return qc


if __name__ == "__main__":
    qc = build_toy_qpe()

    print("Circuit:")
    print(qc)

    sv = Statevector.from_instruction(qc)
    probs = sv.probabilities_dict(qargs=[0, 1])

    print("\nProbabilities on estimation register:")
    print(probs)

    most_likely = max(probs, key=probs.get)
    print("Most likely bitstring:", most_likely)

    print("\nProbabilities on estimation register (reversed order):")
    print(sv.probabilities_dict(qargs=[1, 0]))
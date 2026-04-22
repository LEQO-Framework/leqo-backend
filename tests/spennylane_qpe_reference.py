import numpy as np
import pennylane as qml



dev = qml.device("lightning.qubit", wires=3)


@qml.qnode(dev)
def qpe_reference():
  
    qml.PauliX(wires=2)  

   
    unitary = qml.PhaseShift(2 * np.pi * 0.25, wires=2)

    qml.QuantumPhaseEstimation(
        unitary,
        estimation_wires=[0, 1],
    )

    return qml.probs(wires=[0, 1])


if __name__ == "__main__":
    probs = qpe_reference()
    print("Probabilities:", probs)
    print("Most likely index:", int(np.argmax(probs)))
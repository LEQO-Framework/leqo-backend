"""
Extends functionality of the :mod:`openqasm3` module required for the leqo-backend.
"""

from typing import Literal

OneQubitGate = Literal["x", "y", "z", "h", "s", "sdg", "t", "tdg", "sx"]
TwoQubitGate = Literal["cx", "cy", "cz", "ch", "swap"]
ThreeQubitGate = Literal["ccx"]

OneQubitGateWithAngle = Literal["rx", "ry", "rz"]
TwoQubitGateWithParam = Literal["cp"]
TwoQubitGateWithAngle = Literal["crx", "cry", "crz"]

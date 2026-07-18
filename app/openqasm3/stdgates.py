"""
List of gates from the `stdgates.inc` header.

https://openqasm.com/language/standard_library.html#api-documentation
"""

from typing import Literal

OneQubitGate = Literal["x", "y", "z", "h", "s", "sdg", "t", "tdg", "sx"]
TwoQubitGate = Literal["cx", "cy", "cz", "ch", "swap"]
ThreeQubitGate = Literal["ccx", "cswap"]

OneQubitGateWithAngle = Literal["rx", "ry", "rz", "p"]
TwoQubitGateWithParam = Literal["cp"]
TwoQubitGateWithParams = Literal["cu"]
TwoQubitGateWithAngle = Literal["crx", "cry", "crz"]

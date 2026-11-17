from app.enricher import Enricher
from app.enricher.gates import GateEnricherStrategy
from app.model.CompileRequest import OptimizeSettings
from app.transformation_manager import MergingProcessor
from app.transformation_manager.frontend_graph import FrontendGraph

H_IMPL = """
OPENQASM 3.1;
@leqo.input 0
qubit[1] q;
h q;
@leqo.output 0
let _out = q;
"""
X_IMPL = """
OPENQASM 3.1;
@leqo.input 0
qubit[1] q;
x q;
@leqo.output 0
let _out = q;
"""
# Flips the input only if the ancilla starts clean, as it is left dirty.
X_VIA_ANCILLA_IMPL = """
OPENQASM 3.1;
include "stdgates.inc";
@leqo.input 0
qubit[1] q;
qubit[1] anc;
x anc;
cx anc, q;
@leqo.output 0
let _out = q;
"""


class DummyOptimizeSettings(OptimizeSettings):
    optimizeWidth = None
    optimizeDepth = None


build_graph = MergingProcessor(
    Enricher(
        GateEnricherStrategy(),
    ),
    FrontendGraph(),
    DummyOptimizeSettings(),
)._build_inner_graph

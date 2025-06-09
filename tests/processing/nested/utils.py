from app.enricher import Enricher
from app.enricher.gates import GateEnricherStrategy
from app.model.CompileRequest import OptimizeSettings
from app.processing import CommonProcessor
from app.processing.frontend_graph import FrontendGraph

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


class DummyOptimizeSettings(OptimizeSettings):
    optimizeWidth = None
    optimizeDepth = None


build_graph = CommonProcessor(
    Enricher(
        GateEnricherStrategy(),
    ),
    FrontendGraph(),
    DummyOptimizeSettings(),
)._build_inner_graph

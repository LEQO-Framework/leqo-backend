import math

import pytest

from app.enricher import Constraints
from app.enricher.encode_value import EncodeValueEnricherStrategy
from app.model.CompileRequest import EncodeValueNode as FrontendEncodeValueNode
from app.model.data_types import (
    ArrayType,
    BitType,
    BoolType,
    FloatType,
    IntType,
)
from app.openqasm3.printer import leqo_dumps

# Define all scenarios requested by the supervisor
ANGLE_SCENARIOS = [
    # Label, Data Type, Value(s)
    ("Empty Array", ArrayType(FloatType(32), 0), []),
    ("All Zeros", ArrayType(FloatType(32), 3), [0.0, 0.0, 0.0]),
    ("Single Non-Zero", ArrayType(FloatType(32), 3), [10.0, 0.0, 0.0]),
    ("All Equal Positive", ArrayType(FloatType(32), 3), [1.0, 1.0, 1.0]),
    ("Mixed Positive", ArrayType(FloatType(32), 3), [1.5, 2.0, 6.0]),
    ("Single Negative", ArrayType(FloatType(32), 2), [-1.0, 1.0]),
    ("All Negative", ArrayType(FloatType(32), 2), [-1.0, -2.0]),
    ("Mixed with Zero", ArrayType(FloatType(32), 3), [-1.0, 0.0, 1.0]),
    ("Magnitude Inv (1,2,3)", ArrayType(IntType(32), 3), [1, 2, 3]),
    ("Magnitude Inv (10,20,30)", ArrayType(IntType(32), 3), [10, 20, 30]),
    ("Numerical Precision", ArrayType(FloatType(64), 2), [1.0, 1.0 + 1e-15]),
    ("Length 1", ArrayType(FloatType(32), 1), [5.0]),
    ("Boundary [0, pi/2]", ArrayType(FloatType(32), 3), [math.pi / 2, 0.0, 0.0]),
    # Critical Scalars
    ("Scalar Float 0.0", FloatType(32), 0.0),
    ("Scalar Float -1.0", FloatType(32), -1.0),
    ("Scalar Float pi/2", FloatType(32), math.pi / 2),
    ("Scalar Float 2pi", FloatType(32), 2 * math.pi),
    ("Scalar Int8 255", IntType(8), 255),
    ("Scalar Int32 Max", IntType(32), 2**31 - 1),
    ("Scalar Bit 1", BitType(size=1), 1),
    ("Scalar Bool True", BoolType(), True),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("label", "data_type", "value"), ANGLE_SCENARIOS)
async def test_angle_encoding_report(engine, label, data_type, value):
    """Generates the QASM for the supervisor's normalization evaluation."""
    node = FrontendEncodeValueNode(id="1", type="encode", encoding="angle", bounds=0)
    constraints = Constraints(
        requested_inputs={0: data_type},
        requested_input_values={0: value},
        optimizeDepth=True,
        optimizeWidth=True,
    )

    strategy = EncodeValueEnricherStrategy(engine)
    results = list(await strategy.enrich(node, constraints))

    print(f"\n{'#' * 30}")
    print(f"SCENARIO: {label}")
    print(f"TYPE: {data_type}")
    print(f"INPUT: {value}")

    if not results:
        print("RESULT: No enrichment generated.")
    else:
        res = results[0]
        impl = res.enriched_node.implementation
        # Convert AST to String if necessary
        qasm = impl if isinstance(impl, str) else leqo_dumps(impl)
        print("GENERATED OPENQASM:")
        print(qasm.strip())
    print(f"{'#' * 30}\n")

from collections.abc import Callable

from openqasm3 import ast

from app.enricher import Constraints, EnrichmentResult
from app.enricher.encode_value_handlers.amplitude import generate_amplitude_enrichment
from app.enricher.encode_value_handlers.matrix import generate_matrix_enrichment
from app.model import CompileRequest, data_types
from app.model.exceptions import InputCountMismatch


CheckConstraints = Callable[
    [CompileRequest.EncodeValueNode, dict[int, data_types.LeqoSupportedType]],
    None,
]

Handler = Callable[
    [CompileRequest.EncodeValueNode, Constraints],
    EnrichmentResult,
]

ENCODE_VALUE_HANDLERS: dict[str, Handler] = {
    "amplitude": generate_amplitude_enrichment,
    "matrix": generate_matrix_enrichment,
}


def try_generate_encode_value_handler(
    node: CompileRequest.Node,
    constraints: Constraints | None,
    check_constraints: CheckConstraints,
) -> list[EnrichmentResult] | None:
    if not isinstance(node, CompileRequest.EncodeValueNode):
        return None

    handler = ENCODE_VALUE_HANDLERS.get(node.encoding)
    if handler is None:
        return None

    if constraints is None:
        raise InputCountMismatch(
            node,
            actual=0,
            should_be="equal",
            expected=1,
        )

    requested_input = constraints.requested_inputs.get(0)

    if node.encoding in {"amplitude", "matrix"} and not isinstance(
        requested_input,
        (data_types.ArrayType, ast.ArrayType),
    ):
        return None

    check_constraints(node, constraints.requested_inputs)

    return [handler(node, constraints)]

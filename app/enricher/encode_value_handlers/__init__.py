from collections.abc import Callable

from app.enricher import Constraints, EnrichmentResult
from app.enricher.encode_value_handlers.amplitude import generate_amplitude_enrichment
from app.model import CompileRequest, data_types
from app.model.exceptions import InputCountMismatch


CheckConstraints = Callable[
    [CompileRequest.EncodeValueNode, dict[int, data_types.LeqoSupportedType]],
    None,
]


def try_generate_encode_value_handler(
    node: CompileRequest.Node,
    constraints: Constraints | None,
    check_constraints: CheckConstraints,
) -> list[EnrichmentResult] | None:
    if not isinstance(node, CompileRequest.EncodeValueNode):
        return None

    if node.encoding != "amplitude":
        return None

    if constraints is None:
        raise InputCountMismatch(
            node,
            actual=0,
            should_be="equal",
            expected=1,
        )

    check_constraints(node, constraints.requested_inputs)

    return [generate_amplitude_enrichment(node, constraints)]

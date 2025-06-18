"""
All diagnostic exceptions that might be thrown during enrichment.
"""

from abc import ABC

from app.model.CompileRequest import (
    EncodeValueNode,
    GateNode,
    MeasurementNode,
    Node,
    ParameterizedGateNode,
    PrepareStateNode,
)
from app.model.exceptions import DiagnosticError


class EnricherException(DiagnosticError, ABC):
    """
    Baseclass for exceptions raised by :class:`~app.enricher.EnricherStrategy`.
    """


class EnrichmentFailed(EnricherException, BaseExceptionGroup):
    def __init__(self, node: Node, exceptions: list[Exception]):
        msg = "Enrichment failed"
        EnricherException.__init__(self, msg, node)
        BaseExceptionGroup.__init__(self, msg, exceptions)

    @staticmethod
    def __new__(cls, _node: Node, exceptions: list[Exception]) -> "EnrichmentFailed":
        msg = "Enrichment failed"
        return BaseExceptionGroup.__new__(cls, msg, exceptions)


class NoImplementationFound(EnricherException):
    def __init__(self, node: Node) -> None:
        super().__init__("No implementations were found", node)


class EncodingNotSupported(EnricherException):
    def __init__(self, node: EncodeValueNode) -> None:
        super().__init__(f"Encoding '{node.encoding}' not supported", node)


class QuantumStateNotSupported(EnricherException):
    def __init__(self, node: PrepareStateNode) -> None:
        super().__init__(f"Quantum state '{node.quantumState}' not supported", node)


class PrepareStateSizeOutOfRange(EnricherException):
    def __init__(self, node: PrepareStateNode) -> None:
        super().__init__(f"Size below 1 is not supported. Got {node.size}.", node)


class BoundsOutOfRange(EnricherException):
    def __init__(self, node: EncodeValueNode) -> None:
        super().__init__(f"Bounds '{node.bounds}' must be between 0 and 1", node)


class GateNotSupported(EnricherException):
    def __init__(self, node: GateNode | ParameterizedGateNode) -> None:
        super().__init__(f"Gate '{node.gate}' not supported", node)


class InvalidSingleQubitIndex(EnricherException):
    def __init__(self, node: MeasurementNode) -> None:
        super().__init__(
            "Single qubit can only be measured with [] or [0] indices", node
        )


class NoIndices(EnricherException):
    def __init__(self, node: MeasurementNode) -> None:
        super().__init__("No indices were specified", node)


class IndicesOutOfRange(EnricherException):
    def __init__(
        self, node: MeasurementNode, out_of_range_indices: list[int], input_size: int
    ) -> None:
        super().__init__(
            f"Indices {out_of_range_indices} out of range [0, {input_size})", node
        )


class DuplicateIndices(EnricherException):
    def __init__(self, node: MeasurementNode, duplicate_indices: list[int]) -> None:
        super().__init__(f"Duplicate indices {duplicate_indices}", node)

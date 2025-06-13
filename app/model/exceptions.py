from app.model.CompileRequest import Node
from app.model.data_types import LeqoSupportedType


class DiagnosticError(Exception):
    """
    Specified an error that's likely caused by wrong data from a client.
    """

    msg: str
    node: Node | None

    def __init__(self, msg: str, node: Node | None = None) -> None:
        super().__init__(msg)

        self.msg = msg
        self.node = node


class InputCountMismatch(DiagnosticError):
    def __init__(self, node: Node, actual: int, expected: int) -> None:
        super().__init__(f"Node can only have {expected} inputs. Got {actual}.", node)


class InputNull(DiagnosticError):
    def __init__(self, node: Node, input_index: int) -> None:
        super().__init__(f"Expected input at index {input_index} but got none.", node)


class InputTypeMismatch(DiagnosticError):
    def __init__(
        self,
        node: Node,
        input_index: int,
        actual: LeqoSupportedType,
        expected: LeqoSupportedType | str,
    ) -> None:
        super().__init__(
            f"Expected type '{expected}' for input {input_index}. Got '{actual}'.",
            node,
        )


class InputSizeMismatch(DiagnosticError):
    def __init__(
        self,
        node: Node,
        input_index: int,
        actual: int,
        expected: int,
    ) -> None:
        super().__init__(
            f"Expected size {expected} for input {input_index}. Got {actual}.",
            node,
        )

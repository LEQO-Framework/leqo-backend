import traceback
from uuid import UUID

from pydantic import BaseModel
from starlette.responses import JSONResponse


class ErrorResult(BaseModel):
    """The result in case of an exception.

    :param request_id: the id of the request
    :param client: whether we think it was the clients fault
    :param message: human readable message
    :param stacktrace: the python error stacktrace
    :param node: the node id the error occurred in
    """

    request: UUID
    client: bool
    message: str
    stacktrace: str
    node: str | None = None


class ServerError(Exception):
    """Exception used in the whole backend."""

    client: bool
    message: str
    node: str | None

    def __init__(
        self,
        source: str | Exception,
        node: str | None = None,
        client: bool = False,
    ) -> None:
        match source:
            case InvalidInputError() | InternalServerError():
                self.message = source.message
                self.node = node if node is not None else source.node
                self.client = source.client
                self.__cause__ = source
            case str():
                self.message = source
                self.node = node
                self.client = client
            case _:
                self.message = str(source) or type(source).__name__
                self.node = node
                self.client = client
                self.__cause__ = source
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message


class InvalidInputError(ServerError):
    """Exception likely caused by invalid input from client."""

    def __init__(
        self,
        message: str,
        node: str | None = None,
    ) -> None:
        super().__init__(message, node, client=True)


class InternalServerError(ServerError):
    """Exception likely caused by internal bugs."""

    def __init__(
        self,
        message: str,
        node: str | None = None,
    ) -> None:
        super().__init__(message, node, client=False)


def handle_exception(exc: Exception, request_id: UUID) -> ErrorResult:
    """Generate response from server error.

    This has to be called inside a except block to get the stacktrace.
    """
    match exc:
        case ServerError():
            return ErrorResult(
                request=request_id,
                client=exc.client,
                message=exc.message,
                stacktrace=traceback.format_exc(),
                node=exc.node,
            )
        case _:
            return ErrorResult(
                request=request_id,
                client=False,
                message=str(exc) or type(exc).__name__,
                stacktrace=traceback.format_exc(),
                node=None,
            )

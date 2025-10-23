"""
This module defines the data models for the status of a compile request.
It provides classes to model progress, status, and associated timestamps.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.model.exceptions import LeqoProblemDetails


class StatusType(StrEnum):
    """
    Enumeration of possible status values.
    """

    IN_PROGRESS = "in_progress"
    """The operation is still in progress"""

    FAILED = "failed"
    """The operation failed"""

    COMPLETED = "completed"
    """The operation completed successfully"""


class Progress(BaseModel):
    """
    Models the progress of a compile request.
    """

    percentage: int = Field(ge=0, le=100)
    """Progress percentage between 0 and 100."""

    currentStep: str
    """Step that is currently executing."""

    model_config = ConfigDict(use_attribute_docstrings=True)


class StatusBase(BaseModel):
    """
    Models the status of a process.
    """

    uuid: UUID
    """Id of the operation represented by this status."""

    createdAt: datetime
    """When this operation started."""

    progress: Progress
    """Progress of this operation."""

    model_config = ConfigDict(use_attribute_docstrings=True)


class CreatedStatus(StatusBase):
    """
    Models the status of a running operation.
    """

    status: Literal[StatusType.IN_PROGRESS] = StatusType.IN_PROGRESS

    completedAt: None = None
    """This operation is not completed yet."""

    result: None = None
    """The operation does not have a result yet."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    @classmethod
    def init_status(cls, uuid: UUID) -> Self:
        return cls(
            uuid=uuid,
            createdAt=datetime.now(UTC),
            progress=Progress(percentage=0, currentStep="init"),
        )


class SuccessStatus(StatusBase):
    """
    Models the status of a completed operation.
    """

    status: Literal[StatusType.COMPLETED] = StatusType.COMPLETED

    completedAt: datetime
    """When this operation completed successfully."""

    result: str
    """Location of the result of this operation."""

    model_config = ConfigDict(use_attribute_docstrings=True)


class FailedStatus(StatusBase):
    """
    Models the status of a failed operation.
    """

    status: Literal[StatusType.FAILED] = StatusType.FAILED

    completedAt: None = None
    """The operation did not complete (successfully)."""

    result: LeqoProblemDetails
    """Machine-readable error information."""

    model_config = ConfigDict(use_attribute_docstrings=True)


StatusResponse = CreatedStatus | SuccessStatus | FailedStatus

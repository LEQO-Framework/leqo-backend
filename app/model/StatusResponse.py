"""
This module defines the data models for the status of a compile request.
It provides classes to model progress, status, and associated timestamps.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field

from app.model.exceptions import LeqoProblemDetails


class StatusType(StrEnum):
    """
    Enumeration of possible status values.
    """

    IN_PROGRESS = "in progress"
    FAILED = "failed"
    COMPLETED = "completed"


class Progress(BaseModel):
    """
    Models the progress of a compile request.
    """

    percentage: int = Field(
        ge=0, le=100, description="Progress percentage between 0 and 100."
    )
    currentStep: str = Field(description="Step that is currently executing.")


class StatusBase(BaseModel):
    """
    Models the status of a process.
    """

    uuid: UUID = Field(description="Id of the operation represented by this status.")
    createdAt: datetime = Field(description="When this operation started.")
    progress: Progress = Field(description="Progress of this operation.")


class CreatedStatus(StatusBase):
    status: Literal[StatusType.IN_PROGRESS] = StatusType.IN_PROGRESS
    completedAt: None = None
    result: None = None

    @classmethod
    def init_status(cls, uuid: UUID) -> Self:
        return cls(
            uuid=uuid,
            createdAt=datetime.now(UTC),
            progress=Progress(percentage=0, currentStep="init"),
        )


class SuccessStatus(StatusBase):
    status: Literal[StatusType.COMPLETED] = StatusType.COMPLETED
    completedAt: datetime = Field(
        description="When this operation completed successfully."
    )
    result: str = Field(description="Location of the result of this operation.")


class FailedStatus(StatusBase):
    status: Literal[StatusType.FAILED] = StatusType.FAILED
    completedAt: None = None
    result: LeqoProblemDetails = Field(
        description="Machine-readable error information."
    )


StatusResponse = CreatedStatus | SuccessStatus | FailedStatus

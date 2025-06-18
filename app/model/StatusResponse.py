"""
This module defines the data models for the status of a compile request.
It provides classes to model progress, status, and associated timestamps.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel

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

    percentage: int
    currentStep: str


class StatusBase(BaseModel):
    """
    Models the status of a process.
    """

    uuid: UUID
    createdAt: datetime
    progress: Progress


class CreatedStatus(StatusBase):
    status: Literal[StatusType.IN_PROGRESS] = StatusType.IN_PROGRESS

    @classmethod
    def init_status(cls, uuid: UUID) -> Self:
        return cls(
            uuid=uuid,
            createdAt=datetime.now(UTC),
            progress=Progress(percentage=0, currentStep="init"),
        )


class SuccessStatus(StatusBase):
    status: Literal[StatusType.COMPLETED] = StatusType.COMPLETED
    completedAt: datetime
    result: str


class FailedStatus(StatusBase):
    status: Literal[StatusType.FAILED] = StatusType.FAILED
    result: LeqoProblemDetails


StatusResponse = CreatedStatus | SuccessStatus | FailedStatus

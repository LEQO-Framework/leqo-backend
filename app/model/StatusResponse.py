"""
This module defines the data models for the status of a compile request.
It provides classes to model progress, status, and associated timestamps.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel


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


class StatusResponse(BaseModel):
    """
    Models the status of a process.
    """

    uuid: UUID
    status: StatusType
    createdAt: datetime | None
    completedAt: datetime | None
    progress: Progress | None
    result: str | None

    @classmethod
    def init_status(cls, uuid: UUID) -> Self:
        return cls(
            uuid=uuid,
            status=StatusType.IN_PROGRESS,
            createdAt=datetime.now(UTC),
            completedAt=None,
            progress=Progress(percentage=0, currentStep="init"),
            result=None,
        )

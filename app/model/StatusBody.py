from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class StatusType(StrEnum):
    IN_PROGRESS = "in progress"
    COMPLETED = "completed"
    UNKNOWN = "unknown"


class Progress(BaseModel):
    percentage: int
    currentStep: str


class StatusBody(BaseModel):
    uuid: UUID
    status: StatusType
    createdAt: datetime | None
    completedAt: datetime | None
    progress: Progress | None
    result: str | None

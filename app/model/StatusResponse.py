"""
This module defines the data models for the status of a compile request.
It provides classes to model progress, status, and associated timestamps.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.database_model import ProcessStates


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
    
    async def addStatusResponseToDB(self, engine) -> None:
        """Add the :class:`StatusResponse` to the database
        
        :param engine: Database engine to insert the :class:`StatusResponse` in
        """
        process_state = ProcessStates(
            id=self.uuid.int,
            status=self.status,
            createdAt=self.createdAt,
            completedAt=self.completedAt,
            progressPercentage=self.progress.percentage if self.progress else None,
            progressCurrentStep=self.progress.currentStep if self.progress else None,
            result=self.result,
        )

        async with AsyncSession(engine) as session:   
            session.add(process_state)
            await session.commit()

    async def updateStatusResponseInDB(self, engine) -> None:
        """Update the :class:`StatusResponse` in the database
        
        :param engine: Database engine to update the :class:`StatusResponse` in
        """
        async with AsyncSession(engine) as session:
            process_state_db = await session.get(ProcessStates, self.uuid.int)
            if process_state_db:
                process_state_db.status = self.status
                process_state_db.createdAt = self.createdAt or process_state_db.createdAt
                process_state_db.completedAt = self.completedAt or process_state_db.completedAt
                if self.progress:
                    process_state_db.progressPercentage = self.progress.percentage
                    process_state_db.progressCurrentStep = self.progress.currentStep
                process_state_db.result = self.result or process_state_db.result
                await session.commit()

"""Database schema for everything stored in the database."""

from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.model.StatusResponse import StatusType


class Base(DeclarativeBase):
    pass


class ProcessStates(Base):
    """Class to store the states of all current processes
    which await processing or a currently processed.
    """

    __tablename__ = "process_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[StatusType] = mapped_column(nullable=False)
    createdAt: Mapped[datetime] = mapped_column(nullable=True)
    completedAt: Mapped[datetime] = mapped_column(nullable=True)
    progressPercentage: Mapped[int] = mapped_column(nullable=True)
    progressCurrentStep: Mapped[str] = mapped_column(nullable=True)
    result: Mapped[str] = mapped_column(nullable=True)


class ProcessedResults(Base):
    """Class to store the processed results."""

    __tablename__ = "processed_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    results: Mapped[list["ResultImplementation"]] = relationship(
        "ResultImplementation",
        back_populates="processed_result",
        cascade="all, delete-orphan",
    )


class ResultImplementation(Base):
    """Class to store resulting implementations."""

    __tablename__ = "result_implementations"

    id: Mapped[int] = mapped_column(primary_key=True)
    implementation: Mapped[str] = mapped_column(nullable=False)
    processed_result_id: Mapped[int] = mapped_column(
        ForeignKey("processed_results.id"), nullable=False
    )

    processed_result: Mapped["ProcessedResults"] = relationship(
        "ProcessedResults", back_populates="results"
    )

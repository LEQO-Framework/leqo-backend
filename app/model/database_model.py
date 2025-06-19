"""
Database schema for everything stored in the database.
"""

import uuid
from datetime import datetime

from sqlalchemy import UUID, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.model.StatusResponse import StatusType


class Base(DeclarativeBase):
    """
    Base class for database types.
    """


class StatusResponseDb(Base):
    """
    Class to store the states of all current processes
    which await processing or a currently processed.
    """

    __tablename__ = "process_states"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    status: Mapped[StatusType] = mapped_column(nullable=False)
    createdAt: Mapped[datetime] = mapped_column(nullable=False)
    completedAt: Mapped[datetime] = mapped_column(nullable=True)
    progressPercentage: Mapped[int] = mapped_column(nullable=False)
    progressCurrentStep: Mapped[str] = mapped_column(nullable=False)
    result: Mapped[str] = mapped_column(nullable=True)


class CompileResult(Base):
    """
    Store the result of a compile request.
    """

    __tablename__ = "compile_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    implementation: Mapped[str] = mapped_column(nullable=False)


class EnrichResult(Base):
    """
    Store the result of an enrich request.
    """

    __tablename__ = "enrich_result"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    results: Mapped[list["SingleEnrichResult"]] = relationship(
        "SingleEnrichResult",
        back_populates="enrich_result",
        cascade="all, delete-orphan",
    )


class SingleEnrichResult(Base):
    """
    Store the implementation for a node in the context of an enrichment result.
    """

    __tablename__ = "single_enrich_result"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    impl_id: Mapped[str] = mapped_column(nullable=False)
    impl_label: Mapped[str] = mapped_column(nullable=True)
    implementation: Mapped[str] = mapped_column(nullable=False)
    enrich_result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enrich_result.id"), nullable=False
    )

    enrich_result: Mapped["EnrichResult"] = relationship(
        "EnrichResult", back_populates="results"
    )

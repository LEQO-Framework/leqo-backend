"""
Database schema for everything stored in the database.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    UUID,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
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
    result: Mapped[str] = mapped_column(Text, nullable=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    compilationTarget: Mapped[str] = mapped_column(
        String, nullable=False, default="qasm"
    )


class CompileResult(Base):
    """
    Store the result of a compile request.
    """

    __tablename__ = "compile_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    implementation: Mapped[str] = mapped_column(nullable=False)
    compilationTarget: Mapped[str] = mapped_column(
        String, nullable=False, default="qasm"
    )


class CompileRequestPayload(Base):
    """
    Store the original compile request payload.
    """

    __tablename__ = "compile_request_payloads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)


class QuantumResourceModel(Base):
    """
    Store Quantum Resource Model representations for a request.
    """

    __tablename__ = "qrms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    filename: Mapped[str | None] = mapped_column(String, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String, nullable=True)


class ServiceDeploymentModel(Base):
    """
    Store Service Deployment Model representations for a request.
    """

    __tablename__ = "service_deployment_models"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    filename: Mapped[str | None] = mapped_column(String, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String, nullable=True)


class EnrichResult(Base):
    """
    Store the result of an enrich request.
    """

    __tablename__ = "enrich_result"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    compilationTarget: Mapped[str] = mapped_column(
        String, nullable=False, default="qasm"
    )
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


class ExecutionRecord(Base):
    """
    Store one run of the QUBO algorithm selection workflow.

    The structural features (``num_variables``, ``density``, ``variable_names``)
    are stored separately from the input so similar QUBOs can be found by query.
    ``succeeded`` stays ``None`` until the outcome of solving the QUBO with the
    selected algorithm is reported. ``candidate_qualities`` maps candidate labels
    (e.g. ``"QAOA p=1"``) to the solution quality reached with them; only records
    with qualities are used as history.
    """

    __tablename__ = "execution_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    input_qubo: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    num_variables: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    density: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    variable_names: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    selected_algorithm: Mapped[str] = mapped_column(String, nullable=False)
    selected_layers: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_qasm: Mapped[str] = mapped_column(Text, nullable=False)
    selected_qpu: Mapped[str | None] = mapped_column(String, nullable=True)
    selected_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    error_chance: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_evaluations: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False
    )
    succeeded: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    candidate_qualities: Mapped[dict[str, float]] = mapped_column(
        JSON, nullable=False, default=dict
    )

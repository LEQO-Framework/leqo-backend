"""
Database migrations applied at startup.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class Migration:
    """Represents a single migration to be applied once."""

    name: str
    statements: Sequence[str]


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        name="0001_add_compilation_target",
        statements=(
            'ALTER TABLE "process_states" ADD COLUMN IF NOT EXISTS "compilationTarget" VARCHAR',
            'ALTER TABLE "process_states" ALTER COLUMN "compilationTarget" SET DEFAULT \'qasm\'',
            'UPDATE "process_states" SET "compilationTarget" = \'qasm\' WHERE "compilationTarget" IS NULL',
            'ALTER TABLE "process_states" ALTER COLUMN "compilationTarget" SET NOT NULL',
            'ALTER TABLE "compile_results" ADD COLUMN IF NOT EXISTS "compilationTarget" VARCHAR',
            'ALTER TABLE "compile_results" ALTER COLUMN "compilationTarget" SET DEFAULT \'qasm\'',
            'UPDATE "compile_results" SET "compilationTarget" = \'qasm\' WHERE "compilationTarget" IS NULL',
            'ALTER TABLE "compile_results" ALTER COLUMN "compilationTarget" SET NOT NULL',
            'ALTER TABLE "enrich_result" ADD COLUMN IF NOT EXISTS "compilationTarget" VARCHAR',
            'ALTER TABLE "enrich_result" ALTER COLUMN "compilationTarget" SET DEFAULT \'qasm\'',
            'UPDATE "enrich_result" SET "compilationTarget" = \'qasm\' WHERE "compilationTarget" IS NULL',
            'ALTER TABLE "enrich_result" ALTER COLUMN "compilationTarget" SET NOT NULL',
        ),
    ),
    Migration(
        name="0002_add_request_metadata_to_process_states",
        statements=(
            'ALTER TABLE "process_states" ADD COLUMN IF NOT EXISTS "name" VARCHAR',
            'ALTER TABLE "process_states" ADD COLUMN IF NOT EXISTS "description" TEXT',
        ),
    ),
    Migration(
        name="0003_update_in_progress_status_value",
        statements=(
            "DO $$ BEGIN "
            "IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'statustype') "
            "AND EXISTS ("
            "SELECT 1 FROM pg_enum e "
            "JOIN pg_type t ON t.oid = e.enumtypid "
            "WHERE t.typname = 'statustype' AND e.enumlabel = 'in progress'"
            ") THEN "
            "ALTER TYPE \"statustype\" RENAME VALUE 'in progress' TO 'in_progress'; "
            "END IF; "
            "END $$",
        ),
    ),
    Migration(
        name="0004_add_compile_request_payloads",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS "compile_request_payloads" (
                "id" UUID PRIMARY KEY,
                "payload" TEXT NOT NULL
            )
            """,
        ),
    ),
    Migration(
        name="0005_create_qrms_and_service_deployment_models",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS "qrms" (
                "id" UUID PRIMARY KEY,
                "payload" TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS "service_deployment_models" (
                "id" UUID PRIMARY KEY,
                "payload" TEXT NOT NULL
            )
            """,
        ),
    ),
)


async def apply_migrations(conn: AsyncConnection) -> None:
    """Apply pending migrations to the connected database."""

    await conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    )

    result = await conn.execute(text("SELECT name FROM schema_migrations"))
    applied = {row.name for row in result}

    for migration in MIGRATIONS:
        if migration.name in applied:
            continue
        for statement in migration.statements:
            await conn.execute(text(statement))
        await conn.execute(
            text("INSERT INTO schema_migrations (name) VALUES (:name)"),
            {"name": migration.name},
        )

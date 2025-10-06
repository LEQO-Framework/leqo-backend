"""
Database migrations applied at startup.
"""

from dataclasses import dataclass
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import text


@dataclass(frozen=True)
class Migration:
    """Represents a single migration to be applied once."""

    name: str
    statements: Sequence[str]


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        name="0001_add_compilation_target",
        statements=(
            "ALTER TABLE \"process_states\" ADD COLUMN IF NOT EXISTS \"compilationTarget\" VARCHAR",
            "ALTER TABLE \"process_states\" ALTER COLUMN \"compilationTarget\" SET DEFAULT 'qasm'",
            "UPDATE \"process_states\" SET \"compilationTarget\" = 'qasm' WHERE \"compilationTarget\" IS NULL",
            "ALTER TABLE \"process_states\" ALTER COLUMN \"compilationTarget\" SET NOT NULL",
            "ALTER TABLE \"compile_results\" ADD COLUMN IF NOT EXISTS \"compilationTarget\" VARCHAR",
            "ALTER TABLE \"compile_results\" ALTER COLUMN \"compilationTarget\" SET DEFAULT 'qasm'",
            "UPDATE \"compile_results\" SET \"compilationTarget\" = 'qasm' WHERE \"compilationTarget\" IS NULL",
            "ALTER TABLE \"compile_results\" ALTER COLUMN \"compilationTarget\" SET NOT NULL",
            "ALTER TABLE \"enrich_result\" ADD COLUMN IF NOT EXISTS \"compilationTarget\" VARCHAR",
            "ALTER TABLE \"enrich_result\" ALTER COLUMN \"compilationTarget\" SET DEFAULT 'qasm'",
            "UPDATE \"enrich_result\" SET \"compilationTarget\" = 'qasm' WHERE \"compilationTarget\" IS NULL",
            "ALTER TABLE \"enrich_result\" ALTER COLUMN \"compilationTarget\" SET NOT NULL",
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

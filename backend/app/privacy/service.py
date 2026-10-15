from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.ingestion.sqlite_repositories import SQLiteConnectionFactory


@dataclass(frozen=True)
class AccountDeletionReport:
    account_email: str
    deleted_rows: dict[str, int]

    @property
    def total_rows_deleted(self) -> int:
        return sum(self.deleted_rows.values())


class AccountDataDeletionService:
    """Removes every row tied to an account from the ingestion, AI and calendar tables."""

    _TABLES: tuple[str, ...] = (
        "sync_checkpoints",
        "raw_message_metadata",
        "ai_stage_outputs",
        "trip_events",
        "trip_conflicts",
    )

    def __init__(self, connection_factory: SQLiteConnectionFactory) -> None:
        self._connections = connection_factory

    def delete_account_data(self, account_email: str) -> AccountDeletionReport:
        normalized_email = account_email.strip().lower()
        if not normalized_email:
            raise ValueError("account_email must not be empty")

        deleted_rows: dict[str, int] = {}
        with self._connections.connect() as conn:
            existing_tables = _existing_tables(conn)
            for table_name in self._TABLES:
                if table_name not in existing_tables:
                    deleted_rows[table_name] = 0
                    continue
                result = conn.execute(
                    f"DELETE FROM {table_name} WHERE account_email = ?",
                    (normalized_email,),
                )
                deleted_rows[table_name] = int(result.rowcount)
            conn.commit()
        return AccountDeletionReport(account_email=normalized_email, deleted_rows=deleted_rows)


def _existing_tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'",
    ).fetchall()
    return {str(row["name"]) for row in rows}

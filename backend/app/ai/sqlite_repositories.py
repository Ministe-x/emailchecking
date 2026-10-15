from __future__ import annotations

import json
from datetime import datetime

from app.ai.repositories import AIResultRepository, StageOutputRecord
from app.ingestion.sqlite_repositories import SQLiteConnectionFactory


class SQLiteAIResultRepository(AIResultRepository):
    def __init__(self, connection_factory: SQLiteConnectionFactory) -> None:
        self._connections = connection_factory
        self._ensure_tables()

    def upsert_stage_output(self, record: StageOutputRecord) -> None:
        with self._connections.connect() as conn:
            conn.execute(
                """
                INSERT INTO ai_stage_outputs (
                    account_email,
                    message_identity,
                    stage_name,
                    output_json,
                    model_provider,
                    model_name,
                    model_version,
                    attempts,
                    used_fallback,
                    failure_reason,
                    processed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_email, message_identity, stage_name) DO UPDATE SET
                    output_json = excluded.output_json,
                    model_provider = excluded.model_provider,
                    model_name = excluded.model_name,
                    model_version = excluded.model_version,
                    attempts = excluded.attempts,
                    used_fallback = excluded.used_fallback,
                    failure_reason = excluded.failure_reason,
                    processed_at = excluded.processed_at
                """,
                (
                    record.account_email,
                    record.message_identity,
                    record.stage_name,
                    json.dumps(record.output_json),
                    record.model_provider,
                    record.model_name,
                    record.model_version,
                    record.attempts,
                    1 if record.used_fallback else 0,
                    record.failure_reason,
                    record.processed_at.isoformat(),
                ),
            )
            conn.commit()

    def _ensure_tables(self) -> None:
        with self._connections.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS ai_stage_outputs (
                    account_email TEXT NOT NULL,
                    message_identity TEXT NOT NULL,
                    stage_name TEXT NOT NULL,
                    output_json TEXT NOT NULL,
                    model_provider TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    used_fallback INTEGER NOT NULL,
                    failure_reason TEXT NULL,
                    processed_at TEXT NOT NULL,
                    PRIMARY KEY (account_email, message_identity, stage_name)
                );

                CREATE INDEX IF NOT EXISTS idx_ai_outputs_message
                ON ai_stage_outputs (message_identity);
                """
            )
            conn.commit()

    def count_outputs(self) -> int:
        with self._connections.connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM ai_stage_outputs").fetchone()
        if row is None:
            return 0
        return int(row["c"])

    def get_output(
        self, account_email: str, message_identity: str, stage_name: str
    ) -> StageOutputRecord | None:
        with self._connections.connect() as conn:
            row = conn.execute(
                """
                SELECT
                    account_email,
                    message_identity,
                    stage_name,
                    output_json,
                    model_provider,
                    model_name,
                    model_version,
                    attempts,
                    used_fallback,
                    failure_reason,
                    processed_at
                FROM ai_stage_outputs
                WHERE account_email = ? AND message_identity = ? AND stage_name = ?
                """,
                (account_email, message_identity, stage_name),
            ).fetchone()
        if row is None:
            return None
        return StageOutputRecord(
            account_email=row["account_email"],
            message_identity=row["message_identity"],
            stage_name=row["stage_name"],
            output_json=json.loads(row["output_json"]),
            model_provider=row["model_provider"],
            model_name=row["model_name"],
            model_version=row["model_version"],
            attempts=int(row["attempts"]),
            used_fallback=bool(row["used_fallback"]),
            failure_reason=row["failure_reason"],
            processed_at=datetime.fromisoformat(row["processed_at"]),
        )

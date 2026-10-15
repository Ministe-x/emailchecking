from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.ingestion.models import NormalizedMailMessage
from app.ingestion.repositories import CheckpointRepository, MessageMetadataRepository
from app.providers.types import IncrementalCheckpoint, ProviderKind


class SQLiteConnectionFactory:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sync_checkpoints (
                    provider TEXT NOT NULL,
                    account_email TEXT NOT NULL,
                    cursor TEXT NULL,
                    synced_until TEXT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (provider, account_email)
                );

                CREATE TABLE IF NOT EXISTS raw_message_metadata (
                    provider TEXT NOT NULL,
                    account_email TEXT NOT NULL,
                    provider_message_id TEXT NOT NULL,
                    dedup_key TEXT NOT NULL,
                    thread_key TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    sent_at TEXT NULL,
                    labels_json TEXT NOT NULL,
                    raw_payload_json TEXT NOT NULL,
                    ingested_at TEXT NOT NULL,
                    PRIMARY KEY (provider, account_email, provider_message_id)
                );

                CREATE INDEX IF NOT EXISTS idx_raw_message_metadata_dedup
                ON raw_message_metadata (account_email, dedup_key);
                """
            )
            conn.commit()


class SQLiteCheckpointRepository(CheckpointRepository):
    def __init__(self, connection_factory: SQLiteConnectionFactory) -> None:
        self._connections = connection_factory

    def get(self, provider: ProviderKind, account_email: str) -> IncrementalCheckpoint:
        with self._connections.connect() as conn:
            row = conn.execute(
                """
                SELECT cursor, synced_until
                FROM sync_checkpoints
                WHERE provider = ? AND account_email = ?
                """,
                (provider.value, account_email),
            ).fetchone()
        if not row:
            return IncrementalCheckpoint()
        synced_until = _parse_iso_datetime(row["synced_until"])
        return IncrementalCheckpoint(cursor=row["cursor"], synced_until=synced_until)

    def save(
        self, provider: ProviderKind, account_email: str, checkpoint: IncrementalCheckpoint
    ) -> None:
        with self._connections.connect() as conn:
            conn.execute(
                """
                INSERT INTO sync_checkpoints (
                    provider, account_email, cursor, synced_until, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(provider, account_email) DO UPDATE SET
                    cursor = excluded.cursor,
                    synced_until = excluded.synced_until,
                    updated_at = excluded.updated_at
                """,
                (
                    provider.value,
                    account_email,
                    checkpoint.cursor,
                    _to_iso_datetime(checkpoint.synced_until),
                    _to_iso_datetime(datetime.now(timezone.utc)),
                ),
            )
            conn.commit()


class SQLiteMessageMetadataRepository(MessageMetadataRepository):
    def __init__(self, connection_factory: SQLiteConnectionFactory) -> None:
        self._connections = connection_factory

    def has_provider_message(
        self, provider: ProviderKind, account_email: str, provider_message_id: str
    ) -> bool:
        with self._connections.connect() as conn:
            row = conn.execute(
                """
                SELECT 1
                FROM raw_message_metadata
                WHERE provider = ? AND account_email = ? AND provider_message_id = ?
                """,
                (provider.value, account_email, provider_message_id),
            ).fetchone()
        return row is not None

    def has_dedup_key(self, account_email: str, dedup_key: str) -> bool:
        with self._connections.connect() as conn:
            row = conn.execute(
                """
                SELECT 1
                FROM raw_message_metadata
                WHERE account_email = ? AND dedup_key = ?
                """,
                (account_email, dedup_key),
            ).fetchone()
        return row is not None

    def store_batch(self, account_email: str, messages: tuple[NormalizedMailMessage, ...]) -> int:
        stored_count = 0
        with self._connections.connect() as conn:
            for message in messages:
                result = conn.execute(
                    """
                    INSERT OR IGNORE INTO raw_message_metadata (
                        provider,
                        account_email,
                        provider_message_id,
                        dedup_key,
                        thread_key,
                        subject,
                        sent_at,
                        labels_json,
                        raw_payload_json,
                        ingested_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        message.provider.value,
                        account_email,
                        message.message_id,
                        message.dedup_key,
                        message.conversation_key,
                        message.subject,
                        _to_iso_datetime(message.sent_at),
                        json.dumps(list(message.labels)),
                        json.dumps(message.raw_payload),
                        _to_iso_datetime(datetime.now(timezone.utc)),
                    ),
                )
                if result.rowcount > 0:
                    stored_count += 1
            conn.commit()
        return stored_count


def _to_iso_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)

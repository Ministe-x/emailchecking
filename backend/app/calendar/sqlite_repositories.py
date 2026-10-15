from __future__ import annotations

import json
from datetime import datetime, timezone

from app.calendar.models import CalendarCandidate, EventConflict, TripEvent
from app.ingestion.sqlite_repositories import SQLiteConnectionFactory


class SQLiteCalendarCandidateRepository:
    def __init__(self, connection_factory: SQLiteConnectionFactory) -> None:
        self._connections = connection_factory

    def list_candidates(self, account_email: str) -> tuple[CalendarCandidate, ...]:
        with self._connections.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    trip.account_email,
                    trip.message_identity,
                    trip.output_json AS trip_json,
                    ad.output_json AS ad_json,
                    imp.output_json AS importance_json,
                    raw.subject AS subject,
                    raw.sent_at AS sent_at,
                    raw.raw_payload_json AS raw_payload_json
                FROM ai_stage_outputs trip
                JOIN ai_stage_outputs ad
                  ON ad.account_email = trip.account_email
                 AND ad.message_identity = trip.message_identity
                 AND ad.stage_name = 'ad_filter'
                JOIN ai_stage_outputs imp
                  ON imp.account_email = trip.account_email
                 AND imp.message_identity = trip.message_identity
                 AND imp.stage_name = 'importance'
                LEFT JOIN raw_message_metadata raw
                  ON raw.account_email = trip.account_email
                 AND (
                        raw.dedup_key = trip.message_identity
                     OR trip.message_identity = raw.provider || ':' || raw.provider_message_id
                 )
                WHERE trip.account_email = ?
                  AND trip.stage_name = 'trip_relevance'
                """,
                (account_email,),
            ).fetchall()

        candidates: list[CalendarCandidate] = []
        for row in rows:
            trip_json = _parse_json_dict(row["trip_json"])
            ad_json = _parse_json_dict(row["ad_json"])
            importance_json = _parse_json_dict(row["importance_json"])
            if bool(ad_json.get("isAd")):
                continue
            if not bool(trip_json.get("isTripRelated")):
                continue

            raw_payload = _parse_json_dict(row["raw_payload_json"])
            source_email = str(raw_payload.get("from") or "").strip().lower() or "unknown"
            plain_body = str(raw_payload.get("plain_body") or "").strip()
            sent_at = _from_iso(row["sent_at"]) or _from_iso(raw_payload.get("sent_at"))
            candidates.append(
                CalendarCandidate(
                    account_email=row["account_email"],
                    message_identity=row["message_identity"],
                    subject=str(row["subject"] or "").strip(),
                    plain_body=plain_body,
                    sent_at=sent_at,
                    source_email=source_email,
                    trip_type=str(trip_json.get("tripType") or "other"),
                    priority_score=int(importance_json.get("priorityScore") or 0),
                    ad_confidence=float(ad_json.get("confidence") or 0.0),
                )
            )
        return tuple(candidates)


class SQLiteTripEventRepository:
    def __init__(self, connection_factory: SQLiteConnectionFactory) -> None:
        self._connections = connection_factory
        self._ensure_tables()

    def replace_for_account(self, account_email: str, events: tuple[TripEvent, ...]) -> None:
        keep_ids = {event.event_id for event in events}
        with self._connections.connect() as conn:
            if keep_ids:
                placeholders = ",".join("?" for _ in keep_ids)
                conn.execute(
                    f"""
                    DELETE FROM trip_events
                    WHERE account_email = ?
                      AND event_id NOT IN ({placeholders})
                    """,
                    (account_email, *sorted(keep_ids)),
                )
            else:
                conn.execute(
                    """
                    DELETE FROM trip_events
                    WHERE account_email = ?
                    """,
                    (account_email,),
                )

            for event in events:
                now = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    """
                    INSERT INTO trip_events (
                        account_email,
                        event_id,
                        message_identity,
                        title,
                        start_at,
                        end_at,
                        timezone,
                        location,
                        booking_ref,
                        source_email,
                        trip_type,
                        priority_score,
                        confidence,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(account_email, event_id) DO UPDATE SET
                        message_identity = excluded.message_identity,
                        title = excluded.title,
                        start_at = excluded.start_at,
                        end_at = excluded.end_at,
                        timezone = excluded.timezone,
                        location = excluded.location,
                        booking_ref = excluded.booking_ref,
                        source_email = excluded.source_email,
                        trip_type = excluded.trip_type,
                        priority_score = excluded.priority_score,
                        confidence = excluded.confidence,
                        updated_at = excluded.updated_at
                    """,
                    (
                        event.account_email,
                        event.event_id,
                        event.message_identity,
                        event.title,
                        event.start_at.isoformat(),
                        event.end_at.isoformat(),
                        event.timezone,
                        event.location,
                        event.booking_ref,
                        event.source_email,
                        event.trip_type,
                        event.priority_score,
                        event.confidence,
                        now,
                        now,
                    ),
                )
            conn.commit()

    def list_upcoming(self, *, account_email: str, now: datetime) -> tuple[TripEvent, ...]:
        with self._connections.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    account_email,
                    event_id,
                    message_identity,
                    title,
                    start_at,
                    end_at,
                    timezone,
                    location,
                    booking_ref,
                    source_email,
                    trip_type,
                    priority_score,
                    confidence
                FROM trip_events
                WHERE account_email = ? AND end_at >= ?
                ORDER BY start_at ASC
                """,
                (account_email, now.isoformat()),
            ).fetchall()

        return tuple(_trip_event_from_row(row) for row in rows)

    def _ensure_tables(self) -> None:
        with self._connections.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS trip_events (
                    account_email TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    message_identity TEXT NOT NULL,
                    title TEXT NOT NULL,
                    start_at TEXT NOT NULL,
                    end_at TEXT NOT NULL,
                    timezone TEXT NOT NULL,
                    location TEXT NULL,
                    booking_ref TEXT NULL,
                    source_email TEXT NOT NULL,
                    trip_type TEXT NOT NULL,
                    priority_score INTEGER NOT NULL,
                    confidence REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (account_email, event_id)
                );

                CREATE INDEX IF NOT EXISTS idx_trip_events_account_time
                ON trip_events (account_email, start_at);
                """
            )
            conn.commit()


class SQLiteConflictRepository:
    def __init__(self, connection_factory: SQLiteConnectionFactory) -> None:
        self._connections = connection_factory
        self._ensure_tables()

    def replace_for_account(self, account_email: str, conflicts: tuple[EventConflict, ...]) -> None:
        with self._connections.connect() as conn:
            conn.execute(
                """
                DELETE FROM trip_conflicts
                WHERE account_email = ?
                """,
                (account_email,),
            )
            for conflict in conflicts:
                conn.execute(
                    """
                    INSERT INTO trip_conflicts (
                        account_email,
                        conflict_id,
                        event_id,
                        other_event_id,
                        conflict_type,
                        detail,
                        detected_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        conflict.account_email,
                        conflict.conflict_id,
                        conflict.event_id,
                        conflict.other_event_id,
                        conflict.conflict_type,
                        conflict.detail,
                        conflict.detected_at.isoformat(),
                    ),
                )
            conn.commit()

    def list_for_account(self, account_email: str) -> tuple[EventConflict, ...]:
        with self._connections.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    account_email,
                    conflict_id,
                    event_id,
                    other_event_id,
                    conflict_type,
                    detail,
                    detected_at
                FROM trip_conflicts
                WHERE account_email = ?
                ORDER BY detected_at DESC
                """,
                (account_email,),
            ).fetchall()
        return tuple(_conflict_from_row(row) for row in rows)

    def _ensure_tables(self) -> None:
        with self._connections.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS trip_conflicts (
                    account_email TEXT NOT NULL,
                    conflict_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    other_event_id TEXT NOT NULL,
                    conflict_type TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    detected_at TEXT NOT NULL,
                    PRIMARY KEY (account_email, conflict_id)
                );

                CREATE INDEX IF NOT EXISTS idx_trip_conflicts_account
                ON trip_conflicts (account_email, event_id);
                """
            )
            conn.commit()


def _trip_event_from_row(row: object) -> TripEvent:
    return TripEvent(
        account_email=row["account_email"],
        event_id=row["event_id"],
        message_identity=row["message_identity"],
        title=row["title"],
        start_at=datetime.fromisoformat(row["start_at"]),
        end_at=datetime.fromisoformat(row["end_at"]),
        timezone=row["timezone"],
        location=row["location"],
        booking_ref=row["booking_ref"],
        source_email=row["source_email"],
        priority_score=int(row["priority_score"]),
        confidence=float(row["confidence"]),
        trip_type=row["trip_type"],
    )


def _conflict_from_row(row: object) -> EventConflict:
    return EventConflict(
        account_email=row["account_email"],
        conflict_id=row["conflict_id"],
        event_id=row["event_id"],
        other_event_id=row["other_event_id"],
        conflict_type=row["conflict_type"],
        detail=row["detail"],
        detected_at=datetime.fromisoformat(row["detected_at"]),
    )


def _parse_json_dict(raw: object) -> dict[str, object]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return {}
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if isinstance(loaded, dict):
        return loaded
    return {}


def _from_iso(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None

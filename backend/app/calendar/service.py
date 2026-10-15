from __future__ import annotations

from datetime import datetime, timezone

from app.calendar.conflicts import detect_conflicts
from app.calendar.extractor import extract_event, rank_events
from app.calendar.models import EventConflict, TimelineResult, TripEvent
from app.calendar.sqlite_repositories import (
    SQLiteCalendarCandidateRepository,
    SQLiteConflictRepository,
    SQLiteTripEventRepository,
)


class CalendarTimelineService:
    def __init__(
        self,
        candidate_repository: SQLiteCalendarCandidateRepository,
        event_repository: SQLiteTripEventRepository,
        conflict_repository: SQLiteConflictRepository,
    ) -> None:
        self._candidates = candidate_repository
        self._events = event_repository
        self._conflicts = conflict_repository

    def refresh_account(self, *, account_email: str, now: datetime | None = None) -> TimelineResult:
        timestamp = _ensure_utc(now)
        candidates = self._candidates.list_candidates(account_email)
        extracted = tuple(extract_event(candidate) for candidate in candidates)
        self._events.replace_for_account(account_email, extracted)

        conflicts = detect_conflicts(
            account_email=account_email, events=extracted, detected_at=timestamp
        )
        self._conflicts.replace_for_account(account_email, conflicts)

        upcoming = self._events.list_upcoming(account_email=account_email, now=timestamp)
        ranked = rank_events(upcoming)
        relevant_conflicts = _conflicts_touching(
            self._conflicts.list_for_account(account_email), ranked
        )
        return TimelineResult(events=ranked, conflicts=relevant_conflicts)

    def get_upcoming_timeline(
        self, *, account_email: str, now: datetime | None = None, limit: int = 50
    ) -> TimelineResult:
        timestamp = _ensure_utc(now)
        upcoming = self._events.list_upcoming(account_email=account_email, now=timestamp)
        ranked = rank_events(upcoming)[: max(0, limit)]
        conflicts = _conflicts_touching(self._conflicts.list_for_account(account_email), ranked)
        return TimelineResult(events=ranked, conflicts=conflicts)

    def get_upcoming_timeline_payload(
        self, *, account_email: str, now: datetime | None = None, limit: int = 50
    ) -> dict[str, object]:
        timeline = self.get_upcoming_timeline(account_email=account_email, now=now, limit=limit)
        return {
            "events": [event.to_timeline_json() for event in timeline.events],
            "conflicts": [conflict.to_timeline_json() for conflict in timeline.conflicts],
        }


def _conflicts_touching(
    conflicts: tuple[EventConflict, ...], events: tuple[TripEvent, ...]
) -> tuple[EventConflict, ...]:
    event_ids = {event.event_id for event in events}
    return tuple(
        conflict
        for conflict in conflicts
        if conflict.event_id in event_ids or conflict.other_event_id in event_ids
    )


def _ensure_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value

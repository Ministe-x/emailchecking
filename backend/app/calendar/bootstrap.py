from __future__ import annotations

from app.calendar.service import CalendarTimelineService
from app.calendar.sqlite_repositories import (
    SQLiteCalendarCandidateRepository,
    SQLiteConflictRepository,
    SQLiteTripEventRepository,
)
from app.ingestion.sqlite_repositories import SQLiteConnectionFactory


def build_calendar_timeline_service(*, db_path: str) -> CalendarTimelineService:
    connections = SQLiteConnectionFactory(db_path)
    return CalendarTimelineService(
        candidate_repository=SQLiteCalendarCandidateRepository(connections),
        event_repository=SQLiteTripEventRepository(connections),
        conflict_repository=SQLiteConflictRepository(connections),
    )

from __future__ import annotations

from datetime import datetime

from app.calendar.service import CalendarTimelineService


def get_upcoming_timeline(
    service: CalendarTimelineService,
    *,
    account_email: str,
    now: datetime | None = None,
    limit: int = 50,
) -> dict[str, object]:
    """Timeline payload consumed by the Apple client (shape documented in apple-app/README.md)."""
    return service.get_upcoming_timeline_payload(
        account_email=account_email,
        now=now,
        limit=limit,
    )

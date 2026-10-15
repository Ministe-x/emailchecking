from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from app.calendar.models import EventConflict, TripEvent

CONFLICT_OVERLAP = "time_overlap"
CONFLICT_DUPLICATE_BOOKING = "duplicate_booking"


def detect_conflicts(
    *, account_email: str, events: tuple[TripEvent, ...], detected_at: datetime | None = None
) -> tuple[EventConflict, ...]:
    timestamp = detected_at or datetime.now(timezone.utc)
    conflicts: list[EventConflict] = []

    sorted_events = sorted(events, key=lambda event: event.start_at)
    for index, left in enumerate(sorted_events):
        for right in sorted_events[index + 1 :]:
            if right.start_at >= left.end_at:
                break
            if _overlaps(left, right):
                conflicts.append(
                    _build_conflict(
                        account_email=account_email,
                        event_id=left.event_id,
                        other_event_id=right.event_id,
                        conflict_type=CONFLICT_OVERLAP,
                        detail=(
                            f"Events overlap between {left.start_at.isoformat()} and "
                            f"{min(left.end_at, right.end_at).isoformat()}."
                        ),
                        detected_at=timestamp,
                    )
                )

    by_booking_ref: dict[str, list[TripEvent]] = {}
    for event in events:
        if not event.booking_ref:
            continue
        key = event.booking_ref.strip().upper()
        if key:
            by_booking_ref.setdefault(key, []).append(event)

    for booking_ref, grouped in by_booking_ref.items():
        if len(grouped) < 2:
            continue
        grouped_sorted = sorted(grouped, key=lambda event: event.start_at)
        for index, event in enumerate(grouped_sorted):
            for other in grouped_sorted[index + 1 :]:
                conflicts.append(
                    _build_conflict(
                        account_email=account_email,
                        event_id=event.event_id,
                        other_event_id=other.event_id,
                        conflict_type=CONFLICT_DUPLICATE_BOOKING,
                        detail=f"Duplicate booking reference detected: {booking_ref}.",
                        detected_at=timestamp,
                    )
                )

    return tuple(conflicts)


def _overlaps(left: TripEvent, right: TripEvent) -> bool:
    return left.start_at < right.end_at and right.start_at < left.end_at


def _build_conflict(
    *,
    account_email: str,
    event_id: str,
    other_event_id: str,
    conflict_type: str,
    detail: str,
    detected_at: datetime,
) -> EventConflict:
    ordered = tuple(sorted((event_id, other_event_id)))
    basis = "|".join((conflict_type, ordered[0], ordered[1]))
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:20]
    return EventConflict(
        account_email=account_email,
        conflict_id=f"conf_{digest}",
        event_id=ordered[0],
        other_event_id=ordered[1],
        conflict_type=conflict_type,
        detail=detail,
        detected_at=detected_at,
    )

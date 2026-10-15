from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CalendarCandidate:
    account_email: str
    message_identity: str
    subject: str
    plain_body: str
    sent_at: datetime | None
    source_email: str
    trip_type: str
    priority_score: int
    ad_confidence: float


@dataclass(frozen=True)
class TripEvent:
    account_email: str
    event_id: str
    message_identity: str
    title: str
    start_at: datetime
    end_at: datetime
    timezone: str
    location: str | None
    booking_ref: str | None
    source_email: str
    priority_score: int
    confidence: float
    trip_type: str

    def to_timeline_json(self) -> dict[str, object]:
        return {
            "eventId": self.event_id,
            "title": self.title,
            "start": self.start_at.isoformat(),
            "end": self.end_at.isoformat(),
            "timezone": self.timezone,
            "location": self.location,
            "bookingRef": self.booking_ref,
            "sourceEmail": self.source_email,
            "priorityScore": self.priority_score,
            "confidence": self.confidence,
            "tripType": self.trip_type,
        }


@dataclass(frozen=True)
class EventConflict:
    account_email: str
    conflict_id: str
    event_id: str
    other_event_id: str
    conflict_type: str
    detail: str
    detected_at: datetime

    def to_timeline_json(self) -> dict[str, object]:
        return {
            "conflictId": self.conflict_id,
            "eventId": self.event_id,
            "otherEventId": self.other_event_id,
            "type": self.conflict_type,
            "detail": self.detail,
            "detectedAt": self.detected_at.isoformat(),
        }


@dataclass(frozen=True)
class TimelineResult:
    events: tuple[TripEvent, ...]
    conflicts: tuple[EventConflict, ...]

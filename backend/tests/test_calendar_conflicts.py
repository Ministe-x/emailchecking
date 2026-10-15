from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.calendar.conflicts import CONFLICT_DUPLICATE_BOOKING, CONFLICT_OVERLAP, detect_conflicts
from app.calendar.models import TripEvent


def _event(
    *,
    event_id: str,
    start_hour: int,
    end_hour: int,
    booking_ref: str | None = None,
) -> TripEvent:
    return TripEvent(
        account_email="user@example.com",
        event_id=event_id,
        message_identity=f"identity-{event_id}",
        title=f"Event {event_id}",
        start_at=datetime(2026, 11, 2, start_hour, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 11, 2, end_hour, 0, tzinfo=timezone.utc),
        timezone="UTC+00:00",
        location=None,
        booking_ref=booking_ref,
        source_email="sender@example.com",
        priority_score=80,
        confidence=0.9,
        trip_type="flight",
    )


class CalendarConflictDetectionTest(unittest.TestCase):
    def test_detects_time_overlap_and_duplicate_booking(self) -> None:
        first = _event(event_id="evt_a", start_hour=9, end_hour=11, booking_ref="ZXCV12")
        second = _event(event_id="evt_b", start_hour=10, end_hour=12, booking_ref="ZXCV12")
        third = _event(event_id="evt_c", start_hour=13, end_hour=14, booking_ref="QWER99")

        conflicts = detect_conflicts(
            account_email="user@example.com",
            events=(first, second, third),
            detected_at=datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc),
        )
        conflict_types = {conflict.conflict_type for conflict in conflicts}
        self.assertIn(CONFLICT_OVERLAP, conflict_types)
        self.assertIn(CONFLICT_DUPLICATE_BOOKING, conflict_types)
        self.assertEqual(len(conflicts), 2)


if __name__ == "__main__":
    unittest.main()

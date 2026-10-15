from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.calendar.extractor import extract_event
from app.calendar.models import CalendarCandidate


class CalendarExtractorTest(unittest.TestCase):
    def test_extracts_structured_fields_from_trip_text(self) -> None:
        candidate = CalendarCandidate(
            account_email="user@example.com",
            message_identity="rfc822:<trip-1@example.com>",
            subject="Flight confirmation to Berlin",
            plain_body=(
                "Departure 2026-11-02T09:00:00+01:00 arrival 2026-11-02T11:30:00+01:00. "
                "Booking ref: AB12CD. Location: BER Airport."
            ),
            sent_at=datetime(2026, 10, 1, 8, 0, tzinfo=timezone.utc),
            source_email="alerts@airline.example",
            trip_type="flight",
            priority_score=91,
            ad_confidence=0.8,
        )

        event = extract_event(candidate)
        self.assertEqual(event.title, "Flight confirmation to Berlin")
        self.assertEqual(event.timezone, "UTC+01:00")
        self.assertEqual(event.booking_ref, "AB12CD")
        self.assertEqual(event.location, "BER Airport")
        self.assertEqual(event.source_email, "alerts@airline.example")
        self.assertGreater(event.confidence, 0.8)

    def test_falls_back_to_sent_time_when_no_datetime_found(self) -> None:
        sent_at = datetime(2026, 10, 5, 14, 15, tzinfo=timezone.utc)
        candidate = CalendarCandidate(
            account_email="user@example.com",
            message_identity="rfc822:<trip-2@example.com>",
            subject="Conference registration",
            plain_body="Welcome to the conference. Final details soon.",
            sent_at=sent_at,
            source_email="events@conference.example",
            trip_type="meeting",
            priority_score=60,
            ad_confidence=0.7,
        )

        event = extract_event(candidate)
        self.assertEqual(event.start_at, sent_at)
        self.assertEqual(event.end_at, sent_at.replace(hour=15, minute=15))
        self.assertEqual(event.timezone, "UTC+00:00")


if __name__ == "__main__":
    unittest.main()

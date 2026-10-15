from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.ingestion.normalizer import normalize_envelope
from app.providers.types import ProviderKind, RawMessageEnvelope


class NormalizerTest(unittest.TestCase):
    def test_normalize_envelope_maps_required_fields(self) -> None:
        envelope = RawMessageEnvelope(
            provider_message_id="gm-1",
            thread_id="thread-1",
            internal_date=datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc),
            payload={
                "message_id": "gm-1",
                "subject": "Re: Flight Itinerary to Berlin",
                "from": "Airline@example.com",
                "to": ["Traveler@example.com", "friend@example.com"],
                "sent_at": "2026-10-01T09:00:00+00:00",
                "plain_body": "Boarding starts at 07:30",
                "labels": ["INBOX", "CATEGORY_UPDATES"],
                "internet_message_id": "<abc-123@example.com>",
            },
        )

        normalized = normalize_envelope(ProviderKind.GMAIL, envelope)

        self.assertEqual(normalized.message_id, "gm-1")
        self.assertEqual(normalized.subject, "Re: Flight Itinerary to Berlin")
        self.assertEqual(normalized.from_address, "airline@example.com")
        self.assertEqual(normalized.to_addresses, ("traveler@example.com", "friend@example.com"))
        self.assertEqual(normalized.provider, ProviderKind.GMAIL)
        self.assertEqual(normalized.labels, ("inbox", "category_updates"))
        self.assertEqual(normalized.dedup_key, "rfc822:<abc-123@example.com>")
        self.assertEqual(normalized.conversation_key, "thread:thread-1")

    def test_normalize_envelope_builds_content_dedup_without_internet_message_id(self) -> None:
        envelope = RawMessageEnvelope(
            provider_message_id="school-1",
            thread_id=None,
            internal_date=datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc),
            payload={
                "subject": "Fwd: Hotel reservation updated",
                "from": "travel-office@school.edu",
                "to": "student@school.edu",
                "plain_body": "Your booking was changed.",
            },
        )

        normalized = normalize_envelope(ProviderKind.SCHOOL, envelope)

        self.assertTrue(normalized.dedup_key.startswith("content:"))
        self.assertEqual(normalized.conversation_key, "subject:hotel reservation updated")


if __name__ == "__main__":
    unittest.main()

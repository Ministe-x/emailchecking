from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.ingestion.dedup import deduplicate_messages
from app.ingestion.models import NormalizedMailMessage
from app.ingestion.threading import merge_trip_threads
from app.providers.types import ProviderKind


def _message(
    *,
    provider: ProviderKind,
    message_id: str,
    dedup_key: str,
    subject: str,
    body: str,
    conversation_key: str,
    sent_hour: int,
) -> NormalizedMailMessage:
    sent_at = datetime(2026, 10, 1, sent_hour, tzinfo=timezone.utc)
    return NormalizedMailMessage(
        message_id=message_id,
        subject=subject,
        from_address="sender@example.com",
        to_addresses=("recipient@example.com",),
        sent_at=sent_at,
        plain_body=body,
        labels=("inbox",),
        provider=provider,
        provider_thread_id=None,
        conversation_key=conversation_key,
        dedup_key=dedup_key,
        raw_payload={},
    )


class DedupAndThreadMergeTest(unittest.TestCase):
    def test_deduplicate_messages_drops_duplicates_by_dedup_key(self) -> None:
        first = _message(
            provider=ProviderKind.GMAIL,
            message_id="m-1",
            dedup_key="rfc822:<same>",
            subject="Flight booking",
            body="Flight confirmed.",
            conversation_key="subject:flight booking",
            sent_hour=8,
        )
        duplicate = _message(
            provider=ProviderKind.SCHOOL,
            message_id="m-2",
            dedup_key="rfc822:<same>",
            subject="Re: Flight booking",
            body="Flight confirmed.",
            conversation_key="subject:flight booking",
            sent_hour=9,
        )

        result = deduplicate_messages((first, duplicate))

        self.assertEqual(len(result.unique_messages), 1)
        self.assertEqual(result.dropped_count, 1)
        self.assertEqual(result.unique_messages[0].message_id, "m-1")

    def test_merge_trip_threads_groups_by_conversation_key(self) -> None:
        trip_first = _message(
            provider=ProviderKind.GMAIL,
            message_id="m-1",
            dedup_key="key-1",
            subject="Flight booking confirmation",
            body="Your itinerary is attached.",
            conversation_key="subject:flight booking confirmation",
            sent_hour=7,
        )
        trip_second = _message(
            provider=ProviderKind.SCHOOL,
            message_id="m-2",
            dedup_key="key-2",
            subject="Re: Flight booking confirmation",
            body="Travel office follow-up.",
            conversation_key="subject:flight booking confirmation",
            sent_hour=10,
        )
        non_trip = _message(
            provider=ProviderKind.GMAIL,
            message_id="m-3",
            dedup_key="key-3",
            subject="Newsletter update",
            body="Campus news.",
            conversation_key="subject:newsletter update",
            sent_hour=12,
        )

        threads = merge_trip_threads((trip_first, trip_second, non_trip))

        self.assertEqual(len(threads), 1)
        self.assertEqual(threads[0].thread_key, "subject:flight booking confirmation")
        self.assertEqual(threads[0].message_ids, ("m-1", "m-2"))
        self.assertEqual(threads[0].providers, (ProviderKind.GMAIL, ProviderKind.SCHOOL))


if __name__ == "__main__":
    unittest.main()

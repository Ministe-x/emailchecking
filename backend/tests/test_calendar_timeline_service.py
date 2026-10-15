from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone

from app.ai.repositories import StageOutputRecord
from app.ai.sqlite_repositories import SQLiteAIResultRepository
from app.calendar.service import CalendarTimelineService
from app.calendar.sqlite_repositories import (
    SQLiteCalendarCandidateRepository,
    SQLiteConflictRepository,
    SQLiteTripEventRepository,
)
from app.ingestion.models import NormalizedMailMessage
from app.ingestion.sqlite_repositories import (
    SQLiteConnectionFactory,
    SQLiteMessageMetadataRepository,
)
from app.providers.types import ProviderKind


class CalendarTimelineServiceTest(unittest.TestCase):
    def test_refresh_persists_and_returns_ranked_upcoming_timeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/calendar.sqlite3"
            connections = SQLiteConnectionFactory(db_path)
            ai_repo = SQLiteAIResultRepository(connections)
            metadata_repo = SQLiteMessageMetadataRepository(connections)
            service = CalendarTimelineService(
                candidate_repository=SQLiteCalendarCandidateRepository(connections),
                event_repository=SQLiteTripEventRepository(connections),
                conflict_repository=SQLiteConflictRepository(connections),
            )

            messages = (
                NormalizedMailMessage(
                    message_id="gmail-1",
                    subject="Hotel check-in details",
                    from_address="bookings@hotel.example",
                    to_addresses=("user@example.com",),
                    sent_at=datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc),
                    plain_body=(
                        "Check-in 2026-11-20T15:00:00+00:00 checkout 2026-11-22T11:00:00+00:00 "
                        "Booking ref: HOTEL77 location: Berlin Central Hotel"
                    ),
                    labels=("inbox",),
                    provider=ProviderKind.GMAIL,
                    provider_thread_id="thread-1",
                    conversation_key="thread:1",
                    dedup_key="rfc822:<hotel-1@example>",
                    raw_payload={
                        "from": "bookings@hotel.example",
                        "plain_body": (
                            "Check-in 2026-11-20T15:00:00+00:00 checkout 2026-11-22T11:00:00+00:00 "
                            "Booking ref: HOTEL77 location: Berlin Central Hotel"
                        ),
                        "sent_at": "2026-11-01T09:00:00+00:00",
                    },
                ),
                NormalizedMailMessage(
                    message_id="gmail-2",
                    subject="Train boarding pass",
                    from_address="tickets@rail.example",
                    to_addresses=("user@example.com",),
                    sent_at=datetime(2026, 11, 1, 8, 0, tzinfo=timezone.utc),
                    plain_body=(
                        "Departure 2026-11-18T09:00:00+00:00 arrival 2026-11-18T11:00:00+00:00 "
                        "Reference ZX-9911 location: Berlin Hbf"
                    ),
                    labels=("inbox",),
                    provider=ProviderKind.GMAIL,
                    provider_thread_id="thread-2",
                    conversation_key="thread:2",
                    dedup_key="rfc822:<train-1@example>",
                    raw_payload={
                        "from": "tickets@rail.example",
                        "plain_body": (
                            "Departure 2026-11-18T09:00:00+00:00 arrival 2026-11-18T11:00:00+00:00 "
                            "Reference ZX-9911 location: Berlin Hbf"
                        ),
                        "sent_at": "2026-11-01T08:00:00+00:00",
                    },
                ),
            )
            metadata_repo.store_batch("user@example.com", messages)

            self._store_stage_bundle(
                repo=ai_repo,
                account_email="user@example.com",
                message_identity="rfc822:<hotel-1@example>",
                priority=88,
                trip_type="hotel",
            )
            self._store_stage_bundle(
                repo=ai_repo,
                account_email="user@example.com",
                message_identity="rfc822:<train-1@example>",
                priority=55,
                trip_type="train",
            )

            now = datetime(2026, 11, 2, 8, 0, tzinfo=timezone.utc)
            refreshed = service.refresh_account(account_email="user@example.com", now=now)
            payload = service.get_upcoming_timeline_payload(
                account_email="user@example.com",
                now=now,
                limit=10,
            )

            self.assertEqual(len(refreshed.events), 2)
            # Priority-aware ordering puts hotel ahead even though its start time is later.
            self.assertEqual(refreshed.events[0].trip_type, "hotel")
            self.assertEqual(refreshed.events[1].trip_type, "train")
            self.assertEqual(len(payload["events"]), 2)
            self.assertEqual(payload["events"][0]["priorityScore"], 88)
            self.assertEqual(payload["events"][0]["sourceEmail"], "bookings@hotel.example")
            self.assertEqual(len(payload["conflicts"]), 0)

    def _store_stage_bundle(
        self,
        *,
        repo: SQLiteAIResultRepository,
        account_email: str,
        message_identity: str,
        priority: int,
        trip_type: str,
    ) -> None:
        timestamp = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
        for stage_name, output_json in (
            ("ad_filter", {"isAd": False, "reason": "trip update", "confidence": 0.82}),
            ("trip_relevance", {"isTripRelated": True, "tripType": trip_type}),
            (
                "importance",
                {"priorityScore": priority, "importanceReason": "Critical travel event"},
            ),
        ):
            repo.upsert_stage_output(
                StageOutputRecord(
                    account_email=account_email,
                    message_identity=message_identity,
                    stage_name=stage_name,
                    output_json=output_json,
                    model_provider="stub",
                    model_name="deterministic-stub",
                    model_version="v1",
                    attempts=1,
                    used_fallback=False,
                    failure_reason=None,
                    processed_at=timestamp,
                )
            )


if __name__ == "__main__":
    unittest.main()

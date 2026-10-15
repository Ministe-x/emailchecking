from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from app.ingestion.service import MailIngestionService
from app.ingestion.sqlite_repositories import (
    SQLiteCheckpointRepository,
    SQLiteConnectionFactory,
    SQLiteMessageMetadataRepository,
)
from app.providers.base import MailboxProvider
from app.providers.factory import ProviderRegistry
from app.providers.sync import IncrementalSyncResult, TimestampSyncStrategy
from app.providers.types import (
    IncrementalCheckpoint,
    MailboxIdentity,
    OAuthTokenSet,
    ProviderKind,
    RawMessageEnvelope,
)


class _FakeIngestionProvider(MailboxProvider):
    provider_kind = ProviderKind.GMAIL
    default_scopes = ("mail.read",)

    def __init__(self) -> None:
        self.sync_strategy = TimestampSyncStrategy()
        base_time = datetime(2026, 10, 1, 8, tzinfo=timezone.utc)
        self._pages = {
            None: (
                RawMessageEnvelope(
                    provider_message_id="gm-1",
                    thread_id="trip-1",
                    internal_date=base_time,
                    payload={
                        "message_id": "gm-1",
                        "subject": "Flight booking confirmed",
                        "from": "alerts@airline.example",
                        "to": ["user@example.com"],
                        "sent_at": base_time.isoformat(),
                        "plain_body": "Trip booking details",
                        "labels": ["INBOX"],
                        "internet_message_id": "<trip-1@example>",
                    },
                ),
            ),
            "page-2": (
                RawMessageEnvelope(
                    provider_message_id="gm-2",
                    thread_id="trip-1",
                    internal_date=base_time + timedelta(hours=1),
                    payload={
                        "message_id": "gm-2",
                        "subject": "Re: Flight booking confirmed",
                        "from": "user@example.com",
                        "to": ["alerts@airline.example"],
                        "sent_at": (base_time + timedelta(hours=1)).isoformat(),
                        "plain_body": "Can I add baggage?",
                        "labels": ["SENT"],
                        "internet_message_id": "<trip-2@example>",
                    },
                ),
                RawMessageEnvelope(
                    provider_message_id="gm-duplicate",
                    thread_id="trip-1",
                    internal_date=base_time + timedelta(hours=1),
                    payload={
                        "message_id": "gm-duplicate",
                        "subject": "Re: Flight booking confirmed",
                        "from": "user@example.com",
                        "to": ["alerts@airline.example"],
                        "sent_at": (base_time + timedelta(hours=1)).isoformat(),
                        "plain_body": "Can I add baggage?",
                        "labels": ["SENT"],
                        "internet_message_id": "<trip-2@example>",
                    },
                ),
            ),
        }

    def authorization_url(self, state: str) -> str:
        return f"https://example.test/oauth?state={state}"

    def exchange_code(self, code: str) -> OAuthTokenSet:
        return OAuthTokenSet(access_token=code, refresh_token=None, expires_at=None)

    def refresh_tokens(self, token_set: OAuthTokenSet) -> OAuthTokenSet:
        return token_set

    def resolve_identity(self, token_set: OAuthTokenSet) -> MailboxIdentity:
        return MailboxIdentity(
            account_id="fake-account",
            email="user@example.com",
            provider=self.provider_kind,
        )

    def incremental_sync(
        self,
        token_set: OAuthTokenSet,
        checkpoint: IncrementalCheckpoint,
        page_token: str | None = None,
    ) -> IncrementalSyncResult:
        messages = self._pages.get(page_token, ())
        derived = self.sync_strategy.derive_checkpoint(checkpoint, messages)
        next_page_token = "page-2" if page_token is None else None
        return IncrementalSyncResult(
            messages=messages,
            next_checkpoint=IncrementalCheckpoint(
                cursor=next_page_token,
                synced_until=derived.synced_until,
            ),
            next_page_token=next_page_token,
            has_more=next_page_token is not None,
        )


class IngestionServiceCheckpointTest(unittest.TestCase):
    def test_incremental_sync_advances_checkpoint_and_avoids_reinserts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/ingestion.sqlite3"
            connections = SQLiteConnectionFactory(db_path)
            checkpoints = SQLiteCheckpointRepository(connections)
            metadata = SQLiteMessageMetadataRepository(connections)
            registry = ProviderRegistry(_providers={ProviderKind.GMAIL: _FakeIngestionProvider()})
            service = MailIngestionService(registry, checkpoints, metadata)

            token_set = OAuthTokenSet(
                access_token="access",
                refresh_token="refresh",
                expires_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
            )
            first = service.run_incremental_sync(
                provider=ProviderKind.GMAIL,
                account_email="user@example.com",
                token_set=token_set,
            )
            second = service.run_incremental_sync(
                provider=ProviderKind.GMAIL,
                account_email="user@example.com",
                token_set=token_set,
            )

            self.assertEqual(first.fetched_count, 3)
            self.assertEqual(first.stored_count, 2)
            self.assertEqual(first.deduped_count, 1)
            self.assertEqual(first.trip_thread_count, 1)
            self.assertIsNotNone(first.checkpoint.synced_until)

            self.assertEqual(second.stored_count, 0)
            self.assertEqual(second.deduped_count, 0)
            self.assertEqual(second.normalized_count, 3)
            self.assertEqual(first.checkpoint.synced_until, second.checkpoint.synced_until)

            checkpoint_after_second = checkpoints.get(ProviderKind.GMAIL, "user@example.com")
            self.assertEqual(checkpoint_after_second.synced_until, first.checkpoint.synced_until)


if __name__ == "__main__":
    unittest.main()

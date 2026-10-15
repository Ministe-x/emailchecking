from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone

from app.ai.client import DeterministicStubAIModelClient, ModelDescriptor
from app.ai.pipeline import AIPipelineService, RetryPolicy, StageRunner
from app.ai.sqlite_repositories import SQLiteAIResultRepository
from app.ingestion.models import NormalizedMailMessage
from app.ingestion.service import MailIngestionService
from app.ingestion.sqlite_repositories import (
    SQLiteCheckpointRepository,
    SQLiteConnectionFactory,
    SQLiteMessageMetadataRepository,
)
from app.observability.metrics import InMemoryMetricsSink
from app.providers.base import MailboxProvider
from app.providers.factory import ProviderRegistry
from app.providers.sync import IncrementalSyncResult, TimestampSyncStrategy
from app.providers.types import (
    IncrementalCheckpoint,
    OAuthTokenSet,
    ProviderKind,
    RawMessageEnvelope,
)


class ObservabilityHooksTest(unittest.TestCase):
    def test_ingestion_emits_counter_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/obs.sqlite3"
            connections = SQLiteConnectionFactory(db_path)
            checkpoints = SQLiteCheckpointRepository(connections)
            metadata = SQLiteMessageMetadataRepository(connections)
            metrics = InMemoryMetricsSink()
            service = MailIngestionService(
                registry=ProviderRegistry(_providers={ProviderKind.GMAIL: _OneMessageProvider()}),
                checkpoint_repository=checkpoints,
                metadata_repository=metadata,
                metrics=metrics,
            )

            result = service.run_incremental_sync(
                provider=ProviderKind.GMAIL,
                account_email="user@example.com",
                token_set=OAuthTokenSet(access_token="a", refresh_token="r", expires_at=None),
            )

            self.assertEqual(result.stored_count, 1)
            self.assertGreater(metrics.counts["sync.fetched_messages|provider=gmail"], 0)
            self.assertGreater(metrics.counts["sync.stored_messages|provider=gmail"], 0)
            self.assertTrue(any(item["name"] == "sync.finish" for item in metrics.events))

    def test_ai_pipeline_emits_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/obs-ai.sqlite3"
            connections = SQLiteConnectionFactory(db_path)
            repo = SQLiteAIResultRepository(connections)
            metrics = InMemoryMetricsSink()
            runner = StageRunner(
                client=DeterministicStubAIModelClient(),
                model=ModelDescriptor(provider="stub", name="deterministic-stub", version="v1"),
                retry_policy=RetryPolicy(max_attempts=2),
                metrics=metrics,
            )
            service = AIPipelineService(stage_runner=runner, repository=repo, metrics=metrics)

            service.process_messages(
                account_email="user@example.com",
                messages=(self._message(),),
            )

            self.assertEqual(metrics.counts["ai.pipeline.messages"], 1)
            self.assertGreater(metrics.counts["ai.stage.success|fallback=false,stage=ad_filter"], 0)
            self.assertTrue(any(item["name"] == "ai.pipeline.finish" for item in metrics.events))

    def _message(self) -> NormalizedMailMessage:
        return NormalizedMailMessage(
            message_id="gm-1",
            subject="Flight update",
            from_address="alerts@example.com",
            to_addresses=("user@example.com",),
            sent_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
            plain_body="Departure changed.",
            labels=("inbox",),
            provider=ProviderKind.GMAIL,
            provider_thread_id="trip-1",
            conversation_key="thread:trip-1",
            dedup_key="rfc822:<gm-1@example>",
            raw_payload={},
        )


class _OneMessageProvider(MailboxProvider):
    provider_kind = ProviderKind.GMAIL
    default_scopes = ("mail.read",)

    def __init__(self) -> None:
        self.sync_strategy = TimestampSyncStrategy()

    def authorization_url(self, state: str) -> str:
        return f"https://example.test/oauth?state={state}"

    def exchange_code(self, code: str) -> OAuthTokenSet:
        return OAuthTokenSet(access_token=code, refresh_token=None, expires_at=None)

    def refresh_tokens(self, token_set: OAuthTokenSet) -> OAuthTokenSet:
        return token_set

    def resolve_identity(self, token_set: OAuthTokenSet):
        raise NotImplementedError

    def incremental_sync(
        self,
        token_set: OAuthTokenSet,
        checkpoint: IncrementalCheckpoint,
        page_token: str | None = None,
    ) -> IncrementalSyncResult:
        envelope = RawMessageEnvelope(
            provider_message_id="gm-1",
            thread_id="t-1",
            internal_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
            payload={
                "message_id": "gm-1",
                "subject": "Flight",
                "from": "alerts@example.com",
                "to": ["user@example.com"],
                "sent_at": "2026-10-01T00:00:00+00:00",
                "plain_body": "Trip details",
                "labels": ["INBOX"],
                "internet_message_id": "<gm-1@example>",
            },
        )
        return IncrementalSyncResult(
            messages=(envelope,),
            next_checkpoint=IncrementalCheckpoint(cursor=None, synced_until=envelope.internal_date),
            next_page_token=None,
            has_more=False,
        )


if __name__ == "__main__":
    unittest.main()

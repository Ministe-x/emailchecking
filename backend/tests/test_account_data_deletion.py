from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone

from app.ai.repositories import StageOutputRecord
from app.ai.sqlite_repositories import SQLiteAIResultRepository
from app.calendar.sqlite_repositories import SQLiteConflictRepository, SQLiteTripEventRepository
from app.ingestion.models import NormalizedMailMessage
from app.ingestion.sqlite_repositories import (
    SQLiteCheckpointRepository,
    SQLiteConnectionFactory,
    SQLiteMessageMetadataRepository,
)
from app.privacy.service import AccountDataDeletionService
from app.providers.types import IncrementalCheckpoint, ProviderKind


class AccountDataDeletionTest(unittest.TestCase):
    def test_delete_account_data_removes_related_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/erase.sqlite3"
            connections = SQLiteConnectionFactory(db_path)
            metadata = SQLiteMessageMetadataRepository(connections)
            checkpoints = SQLiteCheckpointRepository(connections)
            ai_repo = SQLiteAIResultRepository(connections)
            # The calendar repositories create their tables on construction.
            SQLiteTripEventRepository(connections)
            SQLiteConflictRepository(connections)
            service = AccountDataDeletionService(connections)

            account = "user@example.com"
            other = "other@example.com"
            metadata.store_batch(account, (self._message("m-1"),))
            metadata.store_batch(other, (self._message("m-2"),))
            checkpoints.save(ProviderKind.GMAIL, account, IncrementalCheckpoint(cursor="cursor-1"))
            checkpoints.save(ProviderKind.GMAIL, other, IncrementalCheckpoint(cursor="cursor-2"))
            ai_repo.upsert_stage_output(self._stage_output(account, "m-1", "ad_filter"))
            ai_repo.upsert_stage_output(self._stage_output(other, "m-2", "ad_filter"))

            report = service.delete_account_data(account)

            self.assertEqual(report.account_email, account)
            self.assertGreater(report.total_rows_deleted, 0)
            self.assertFalse(metadata.has_provider_message(ProviderKind.GMAIL, account, "m-1"))
            self.assertTrue(metadata.has_provider_message(ProviderKind.GMAIL, other, "m-2"))
            self.assertIsNone(ai_repo.get_output(account, "m-1", "ad_filter"))
            self.assertIsNotNone(ai_repo.get_output(other, "m-2", "ad_filter"))
            self.assertIsNone(checkpoints.get(ProviderKind.GMAIL, account).cursor)
            self.assertEqual(checkpoints.get(ProviderKind.GMAIL, other).cursor, "cursor-2")

    def test_delete_account_data_rejects_empty_email(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            connections = SQLiteConnectionFactory(f"{tmpdir}/erase.sqlite3")
            service = AccountDataDeletionService(connections)
            with self.assertRaises(ValueError):
                service.delete_account_data("  ")

    def _message(self, message_id: str) -> NormalizedMailMessage:
        return NormalizedMailMessage(
            message_id=message_id,
            subject="Booking",
            from_address="sender@example.com",
            to_addresses=("user@example.com",),
            sent_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
            plain_body="Body",
            labels=("inbox",),
            provider=ProviderKind.GMAIL,
            provider_thread_id="thread",
            conversation_key="thread:1",
            dedup_key=f"dedup:{message_id}",
            raw_payload={"plain_body": "Body"},
        )

    def _stage_output(
        self, account_email: str, message_identity: str, stage_name: str
    ) -> StageOutputRecord:
        return StageOutputRecord(
            account_email=account_email,
            message_identity=message_identity,
            stage_name=stage_name,
            output_json={"isAd": False, "reason": "trip", "confidence": 0.9},
            model_provider="stub",
            model_name="deterministic-stub",
            model_version="v1",
            attempts=1,
            used_fallback=False,
            failure_reason=None,
            processed_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from app.ai.client import (
    STAGE_AD_FILTER,
    STAGE_IMPORTANCE,
    STAGE_TRIP_RELEVANCE,
    DeterministicStubAIModelClient,
    ModelDescriptor,
)
from app.ai.models import TRIP_TYPES
from app.ai.pipeline import AIPipelineService, RetryPolicy, StageRunner
from app.ai.sqlite_repositories import SQLiteAIResultRepository
from app.ingestion.models import NormalizedMailMessage
from app.ingestion.sqlite_repositories import SQLiteConnectionFactory
from app.providers.types import ProviderKind


def _load_fixture_messages() -> tuple[NormalizedMailMessage, ...]:
    fixture_path = Path(__file__).parent / "fixtures" / "ingestion_messages.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    messages: list[NormalizedMailMessage] = []
    for item in data:
        messages.append(
            NormalizedMailMessage(
                message_id=item["message_id"],
                subject=item["subject"],
                from_address=item["from_address"],
                to_addresses=tuple(item["to_addresses"]),
                sent_at=datetime.fromisoformat(item["sent_at"]),
                plain_body=item["plain_body"],
                labels=tuple(item["labels"]),
                provider=ProviderKind(item["provider"]),
                provider_thread_id=item["provider_thread_id"],
                conversation_key=item["conversation_key"],
                dedup_key=item["dedup_key"],
                raw_payload=item["raw_payload"],
            )
        )
    return tuple(messages)


class AIStageContractTest(unittest.TestCase):
    def test_pipeline_contract_and_persistence_with_ingestion_fixture(self) -> None:
        fixture_messages = _load_fixture_messages()
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/ai.sqlite3"
            connections = SQLiteConnectionFactory(db_path)
            repository = SQLiteAIResultRepository(connections)
            service = AIPipelineService(
                stage_runner=StageRunner(
                    client=DeterministicStubAIModelClient(),
                    model=ModelDescriptor(provider="stub", name="deterministic-stub", version="v1"),
                    retry_policy=RetryPolicy(max_attempts=2),
                ),
                repository=repository,
            )

            results = service.process_messages(
                account_email="user@example.com",
                messages=fixture_messages,
            )

            self.assertEqual(len(results), len(fixture_messages))
            for result in results:
                self.assertIsInstance(result.ad_filter.is_ad, bool)
                self.assertGreaterEqual(result.ad_filter.confidence, 0.0)
                self.assertLessEqual(result.ad_filter.confidence, 1.0)
                self.assertIsInstance(result.trip_relevance.is_trip_related, bool)
                self.assertIn(result.trip_relevance.trip_type, TRIP_TYPES)
                self.assertGreaterEqual(result.importance.priority_score, 0)
                self.assertLessEqual(result.importance.priority_score, 100)
                self.assertEqual(result.calendar_seed.message_identity, result.message_identity)

                for stage in (STAGE_AD_FILTER, STAGE_TRIP_RELEVANCE, STAGE_IMPORTANCE):
                    record = repository.get_output(
                        "user@example.com",
                        result.message_identity,
                        stage,
                    )
                    self.assertIsNotNone(record)
                    assert record is not None
                    self.assertEqual(record.model_provider, "stub")
                    self.assertEqual(record.model_name, "deterministic-stub")
                    self.assertEqual(record.model_version, "v1")

            self.assertEqual(repository.count_outputs(), len(fixture_messages) * 3)


if __name__ == "__main__":
    unittest.main()

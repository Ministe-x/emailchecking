from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.ai.client import (
    STAGE_AD_FILTER,
    AIModelClient,
    ModelDescriptor,
    ModelUnavailableError,
)
from app.ai.pipeline import RetryPolicy, StageRunner
from app.ingestion.models import NormalizedMailMessage
from app.providers.types import ProviderKind


class _ScriptedClient(AIModelClient):
    def __init__(self, responses: list[object]) -> None:
        self._responses = responses

    def run_stage(
        self,
        *,
        stage_name: str,
        message: NormalizedMailMessage,
        context: dict[str, object],
    ) -> dict[str, object]:
        if not self._responses:
            raise RuntimeError("No scripted response left")
        next_item = self._responses.pop(0)
        if isinstance(next_item, Exception):
            raise next_item
        if not isinstance(next_item, dict):
            raise ValueError("Scripted output must be dict")
        return next_item


def _message() -> NormalizedMailMessage:
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


class AIRetryFallbackTest(unittest.TestCase):
    def test_stage_runner_retries_then_accepts_valid_output(self) -> None:
        scripted = _ScriptedClient(
            responses=[
                {"isAd": "wrong-type", "reason": "bad", "confidence": 0.9},
                {"isAd": False, "reason": "not an ad", "confidence": 0.8},
            ]
        )
        runner = StageRunner(
            client=scripted,
            model=ModelDescriptor(provider="stub", name="test", version="v1"),
            retry_policy=RetryPolicy(max_attempts=2),
        )

        execution = runner.run_ad_filter(_message())

        self.assertEqual(execution.stage_name, STAGE_AD_FILTER)
        self.assertEqual(execution.attempts, 2)
        self.assertFalse(execution.used_fallback)
        self.assertIsNone(execution.failure_reason)
        self.assertEqual(execution.output_json["isAd"], False)

    def test_stage_runner_falls_back_when_model_is_unavailable(self) -> None:
        scripted = _ScriptedClient(
            responses=[
                ModelUnavailableError("provider timeout"),
                ModelUnavailableError("provider timeout"),
            ]
        )
        runner = StageRunner(
            client=scripted,
            model=ModelDescriptor(provider="stub", name="test", version="v1"),
            retry_policy=RetryPolicy(max_attempts=2),
        )

        execution = runner.run_ad_filter(_message())

        self.assertEqual(execution.stage_name, STAGE_AD_FILTER)
        self.assertEqual(execution.attempts, 2)
        self.assertTrue(execution.used_fallback)
        self.assertIn("provider timeout", execution.failure_reason or "")
        self.assertIn("isAd", execution.output_json)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.providers.sync import TimestampSyncStrategy
from app.providers.types import IncrementalCheckpoint, RawMessageEnvelope


class TimestampSyncStrategyTest(unittest.TestCase):
    def test_build_plan_contains_updated_after_when_checkpoint_exists(self) -> None:
        strategy = TimestampSyncStrategy(updated_after_param="updated_after")
        checkpoint = IncrementalCheckpoint(
            synced_until=datetime(2026, 1, 1, tzinfo=timezone.utc)
        )

        plan = strategy.build_plan(checkpoint)

        self.assertIn("updated_after", plan.query_params)
        self.assertEqual(plan.query_params["updated_after"], "2026-01-01T00:00:00+00:00")

    def test_derive_checkpoint_advances_to_latest_internal_date(self) -> None:
        strategy = TimestampSyncStrategy()
        previous = IncrementalCheckpoint(synced_until=datetime(2026, 1, 1, tzinfo=timezone.utc))
        messages = (
            RawMessageEnvelope(
                provider_message_id="m1",
                thread_id=None,
                internal_date=datetime(2026, 1, 2, tzinfo=timezone.utc),
                payload={},
            ),
            RawMessageEnvelope(
                provider_message_id="m2",
                thread_id=None,
                internal_date=datetime(2026, 1, 3, tzinfo=timezone.utc),
                payload={},
            ),
        )

        next_checkpoint = strategy.derive_checkpoint(previous, messages)

        self.assertEqual(
            next_checkpoint.synced_until,
            datetime(2026, 1, 3, tzinfo=timezone.utc),
        )


if __name__ == "__main__":
    unittest.main()

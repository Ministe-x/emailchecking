from __future__ import annotations

import unittest

from app.ai.schema import (
    SchemaValidationError,
    validate_ad_filter,
    validate_importance,
    validate_trip_relevance,
)


class AISchemaValidationTest(unittest.TestCase):
    def test_validate_ad_filter_accepts_expected_shape(self) -> None:
        output = validate_ad_filter(
            {"isAd": False, "reason": "Transactional message", "confidence": 0.77}
        )
        self.assertFalse(output.is_ad)
        self.assertEqual(output.reason, "Transactional message")
        self.assertAlmostEqual(output.confidence, 0.77)

    def test_validate_trip_relevance_rejects_inconsistent_shape(self) -> None:
        with self.assertRaises(SchemaValidationError):
            validate_trip_relevance({"isTripRelated": False, "tripType": "flight"})

    def test_validate_importance_rejects_out_of_range_score(self) -> None:
        with self.assertRaises(SchemaValidationError):
            validate_importance({"priorityScore": 101, "importanceReason": "Too high"})


if __name__ == "__main__":
    unittest.main()

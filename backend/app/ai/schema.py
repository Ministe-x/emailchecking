from __future__ import annotations

from app.ai.models import TRIP_TYPES, AdFilterOutput, ImportanceOutput, TripRelevanceOutput


class SchemaValidationError(ValueError):
    """Raised when model output does not match expected structured schema."""


def validate_ad_filter(payload: object) -> AdFilterOutput:
    data = _expect_dict(payload, stage_name="ad_filter")
    is_ad = _expect_bool(data, "isAd", stage_name="ad_filter")
    reason = _expect_non_empty_str(data, "reason", stage_name="ad_filter")
    confidence = _expect_float_in_range(
        data, "confidence", minimum=0.0, maximum=1.0, stage_name="ad_filter"
    )
    return AdFilterOutput(is_ad=is_ad, reason=reason, confidence=confidence)


def validate_trip_relevance(payload: object) -> TripRelevanceOutput:
    data = _expect_dict(payload, stage_name="trip_relevance")
    is_trip_related = _expect_bool(data, "isTripRelated", stage_name="trip_relevance")
    trip_type = _expect_non_empty_str(data, "tripType", stage_name="trip_relevance")
    if trip_type not in TRIP_TYPES:
        raise SchemaValidationError(
            f"trip_relevance.tripType must be one of {TRIP_TYPES}; got {trip_type!r}"
        )
    if not is_trip_related and trip_type != "none":
        raise SchemaValidationError(
            "trip_relevance.tripType must be 'none' when isTripRelated is false"
        )
    return TripRelevanceOutput(is_trip_related=is_trip_related, trip_type=trip_type)


def validate_importance(payload: object) -> ImportanceOutput:
    data = _expect_dict(payload, stage_name="importance")
    priority_score = _expect_int_in_range(
        data, "priorityScore", minimum=0, maximum=100, stage_name="importance"
    )
    importance_reason = _expect_non_empty_str(data, "importanceReason", stage_name="importance")
    return ImportanceOutput(priority_score=priority_score, importance_reason=importance_reason)


def _expect_dict(payload: object, *, stage_name: str) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise SchemaValidationError(f"{stage_name} output must be a JSON object")
    return payload


def _expect_bool(data: dict[str, object], key: str, *, stage_name: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise SchemaValidationError(f"{stage_name}.{key} must be a boolean")
    return value


def _expect_non_empty_str(data: dict[str, object], key: str, *, stage_name: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SchemaValidationError(f"{stage_name}.{key} must be a non-empty string")
    return value.strip()


def _expect_float_in_range(
    data: dict[str, object], key: str, *, minimum: float, maximum: float, stage_name: str
) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise SchemaValidationError(f"{stage_name}.{key} must be a number")
    number = float(value)
    if number < minimum or number > maximum:
        raise SchemaValidationError(
            f"{stage_name}.{key} must be within [{minimum}, {maximum}]"
        )
    return number


def _expect_int_in_range(
    data: dict[str, object], key: str, *, minimum: int, maximum: int, stage_name: str
) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SchemaValidationError(f"{stage_name}.{key} must be an integer")
    if value < minimum or value > maximum:
        raise SchemaValidationError(
            f"{stage_name}.{key} must be within [{minimum}, {maximum}]"
        )
    return value

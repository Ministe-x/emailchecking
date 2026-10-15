from __future__ import annotations

from dataclasses import dataclass

from app.ingestion.models import NormalizedMailMessage

TRIP_TYPES: tuple[str, ...] = (
    "flight",
    "hotel",
    "train",
    "meeting",
    "visa",
    "event",
    "car_rental",
    "other",
    "none",
)


@dataclass(frozen=True)
class AdFilterOutput:
    is_ad: bool
    reason: str
    confidence: float

    def to_json(self) -> dict[str, object]:
        return {"isAd": self.is_ad, "reason": self.reason, "confidence": self.confidence}


@dataclass(frozen=True)
class TripRelevanceOutput:
    is_trip_related: bool
    trip_type: str

    def to_json(self) -> dict[str, object]:
        return {"isTripRelated": self.is_trip_related, "tripType": self.trip_type}


@dataclass(frozen=True)
class ImportanceOutput:
    priority_score: int
    importance_reason: str

    def to_json(self) -> dict[str, object]:
        return {"priorityScore": self.priority_score, "importanceReason": self.importance_reason}


@dataclass(frozen=True)
class CalendarSeed:
    message_identity: str
    is_candidate: bool
    trip_type: str
    priority_score: int


@dataclass(frozen=True)
class MessageAIResult:
    message: NormalizedMailMessage
    message_identity: str
    ad_filter: AdFilterOutput
    trip_relevance: TripRelevanceOutput
    importance: ImportanceOutput
    calendar_seed: CalendarSeed


@dataclass(frozen=True)
class StageExecution:
    stage_name: str
    output_json: dict[str, object]
    attempts: int
    used_fallback: bool
    failure_reason: str | None

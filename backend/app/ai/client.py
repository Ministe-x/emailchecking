from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.ai.models import AdFilterOutput, TripRelevanceOutput
from app.ai.rules import rule_based_ad_filter, rule_based_importance, rule_based_trip_relevance
from app.ingestion.models import NormalizedMailMessage

STAGE_AD_FILTER = "ad_filter"
STAGE_TRIP_RELEVANCE = "trip_relevance"
STAGE_IMPORTANCE = "importance"


class ModelUnavailableError(RuntimeError):
    """Raised when the upstream model provider cannot be reached."""


class AIModelClient(Protocol):
    def run_stage(
        self,
        *,
        stage_name: str,
        message: NormalizedMailMessage,
        context: dict[str, object],
    ) -> dict[str, object]:
        ...


@dataclass(frozen=True)
class ModelDescriptor:
    provider: str
    name: str
    version: str


class DeterministicStubAIModelClient:
    """Puts the rule engine behind the model interface until a real provider is added."""

    def run_stage(
        self,
        *,
        stage_name: str,
        message: NormalizedMailMessage,
        context: dict[str, object],
    ) -> dict[str, object]:
        if stage_name == STAGE_AD_FILTER:
            return rule_based_ad_filter(message).to_json()
        if stage_name == STAGE_TRIP_RELEVANCE:
            return rule_based_trip_relevance(message).to_json()
        if stage_name == STAGE_IMPORTANCE:
            ad_payload = context.get(STAGE_AD_FILTER)
            trip_payload = context.get(STAGE_TRIP_RELEVANCE)
            if not isinstance(ad_payload, dict) or not isinstance(trip_payload, dict):
                raise ValueError("importance stage requires ad_filter and trip_relevance context")
            importance = rule_based_importance(
                message,
                ad_filter=AdFilterOutput(
                    is_ad=bool(ad_payload.get("isAd", False)),
                    reason=str(ad_payload.get("reason", "")),
                    confidence=float(ad_payload.get("confidence", 0.5)),
                ),
                trip_relevance=TripRelevanceOutput(
                    is_trip_related=bool(trip_payload.get("isTripRelated", False)),
                    trip_type=str(trip_payload.get("tripType", "none")),
                ),
            )
            return importance.to_json()
        raise ValueError(f"Unsupported stage: {stage_name}")

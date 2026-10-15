from __future__ import annotations

from app.ai.models import AdFilterOutput, ImportanceOutput, TripRelevanceOutput
from app.ingestion.models import NormalizedMailMessage

_AD_KEYWORDS = ("sale", "discount", "promo", "unsubscribe", "newsletter", "deal")
_TRIP_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("flight", "flight"),
    ("hotel", "hotel"),
    ("check-in", "hotel"),
    ("train", "train"),
    ("rail", "train"),
    ("meeting", "meeting"),
    ("conference", "meeting"),
    ("visa", "visa"),
    ("event", "event"),
    ("ticket", "event"),
    ("car rental", "car_rental"),
)


def rule_based_ad_filter(message: NormalizedMailMessage) -> AdFilterOutput:
    content = _content(message)
    is_ad = any(keyword in content for keyword in _AD_KEYWORDS)
    if is_ad:
        return AdFilterOutput(
            is_ad=True,
            reason="Marketing language detected in subject/body.",
            confidence=0.88,
        )
    return AdFilterOutput(
        is_ad=False,
        reason="No strong marketing indicators detected.",
        confidence=0.72,
    )


def rule_based_trip_relevance(message: NormalizedMailMessage) -> TripRelevanceOutput:
    content = _content(message)
    for keyword, trip_type in _TRIP_KEYWORDS:
        if keyword in content:
            return TripRelevanceOutput(is_trip_related=True, trip_type=trip_type)
    return TripRelevanceOutput(is_trip_related=False, trip_type="none")


def rule_based_importance(
    message: NormalizedMailMessage,
    *,
    ad_filter: AdFilterOutput,
    trip_relevance: TripRelevanceOutput,
) -> ImportanceOutput:
    if ad_filter.is_ad:
        return ImportanceOutput(
            priority_score=8,
            importance_reason="Classified as advertisement, deprioritized.",
        )

    content = _content(message)
    score = 20
    reasons: list[str] = []

    if trip_relevance.is_trip_related:
        score += 45
        reasons.append(f"Trip-related ({trip_relevance.trip_type}) content detected.")

    if "urgent" in content or "action required" in content:
        score += 20
        reasons.append("Contains urgency/action language.")

    if "changed" in content or "cancel" in content:
        score += 15
        reasons.append("Mentions updates or cancellations.")

    if "reminder" in content:
        score += 5
        reasons.append("Reminder-style message.")

    clamped = max(0, min(100, score))
    if not reasons:
        reasons.append("General non-promotional inbox message.")
    return ImportanceOutput(priority_score=clamped, importance_reason=" ".join(reasons))


def _content(message: NormalizedMailMessage) -> str:
    labels = " ".join(message.labels)
    return f"{message.subject} {message.plain_body} {labels}".lower()

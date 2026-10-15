from __future__ import annotations

import re
from collections import defaultdict

from app.ingestion.models import NormalizedMailMessage, TripConversationThread

_TRIP_SIGNAL_TERMS = (
    "flight",
    "itinerary",
    "boarding",
    "hotel",
    "reservation",
    "booking",
    "check-in",
    "check in",
    "trip",
    "travel",
    "train",
    "bus",
    "visa",
    "conference",
)
_TOKEN_BOUNDARY_RE = re.compile(r"[^a-z0-9]+")


def merge_trip_threads(
    messages: tuple[NormalizedMailMessage, ...],
) -> tuple[TripConversationThread, ...]:
    grouped: dict[str, list[NormalizedMailMessage]] = defaultdict(list)
    for message in messages:
        if not is_trip_related(message):
            continue
        grouped[message.conversation_key].append(message)

    merged_threads: list[TripConversationThread] = []
    for thread_key, grouped_messages in grouped.items():
        sorted_messages = sorted(
            grouped_messages,
            key=lambda message: (
                message.sent_at.isoformat() if message.sent_at else "",
                message.message_id,
            ),
        )
        participants = sorted(
            {
                participant
                for message in sorted_messages
                for participant in (message.from_address, *message.to_addresses)
                if participant
            }
        )
        providers = tuple(dict.fromkeys(message.provider for message in sorted_messages))
        merged_threads.append(
            TripConversationThread(
                thread_key=thread_key,
                subject=_select_subject(sorted_messages),
                message_ids=tuple(message.message_id for message in sorted_messages),
                participants=tuple(participants),
                started_at=sorted_messages[0].sent_at if sorted_messages else None,
                ended_at=sorted_messages[-1].sent_at if sorted_messages else None,
                providers=providers,
            )
        )

    return tuple(sorted(merged_threads, key=lambda thread: thread.thread_key))


def is_trip_related(message: NormalizedMailMessage) -> bool:
    text = f"{message.subject} {message.plain_body}".lower()
    normalized_text = _TOKEN_BOUNDARY_RE.sub(" ", text)
    return any(signal in normalized_text for signal in _TRIP_SIGNAL_TERMS)


def _select_subject(messages: list[NormalizedMailMessage]) -> str:
    for message in messages:
        if message.subject:
            return message.subject
    return "(no subject)"

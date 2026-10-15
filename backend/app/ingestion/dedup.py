from __future__ import annotations

from dataclasses import dataclass

from app.ingestion.models import NormalizedMailMessage


@dataclass(frozen=True)
class DedupResult:
    unique_messages: tuple[NormalizedMailMessage, ...]
    dropped_count: int


def deduplicate_messages(
    messages: tuple[NormalizedMailMessage, ...],
    *,
    seen_provider_message_ids: set[str] | None = None,
    seen_dedup_keys: set[str] | None = None,
) -> DedupResult:
    provider_id_cache = seen_provider_message_ids or set()
    dedup_key_cache = seen_dedup_keys or set()
    unique: list[NormalizedMailMessage] = []
    dropped_count = 0

    for message in _sorted_messages(messages):
        provider_scoped_id = f"{message.provider.value}:{message.message_id}"
        if provider_scoped_id in provider_id_cache:
            dropped_count += 1
            continue
        if message.dedup_key and message.dedup_key in dedup_key_cache:
            dropped_count += 1
            continue

        unique.append(message)
        provider_id_cache.add(provider_scoped_id)
        if message.dedup_key:
            dedup_key_cache.add(message.dedup_key)

    return DedupResult(unique_messages=tuple(unique), dropped_count=dropped_count)


def _sorted_messages(
    messages: tuple[NormalizedMailMessage, ...],
) -> tuple[NormalizedMailMessage, ...]:
    return tuple(
        sorted(
            messages,
            key=lambda item: (
                item.sent_at.isoformat() if item.sent_at else "",
                item.provider.value,
                item.message_id,
            ),
        )
    )

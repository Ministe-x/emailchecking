from __future__ import annotations

from app.ingestion.models import NormalizedMailMessage


def build_message_identity(message: NormalizedMailMessage) -> str:
    if message.dedup_key:
        return message.dedup_key
    return f"{message.provider.value}:{message.message_id}"

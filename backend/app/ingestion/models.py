from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.providers.types import IncrementalCheckpoint, ProviderKind


@dataclass(frozen=True)
class NormalizedMailMessage:
    message_id: str
    subject: str
    from_address: str
    to_addresses: tuple[str, ...]
    sent_at: datetime | None
    plain_body: str
    labels: tuple[str, ...]
    provider: ProviderKind
    provider_thread_id: str | None = None
    conversation_key: str = ""
    dedup_key: str = ""
    raw_payload: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class TripConversationThread:
    thread_key: str
    subject: str
    message_ids: tuple[str, ...]
    participants: tuple[str, ...]
    started_at: datetime | None
    ended_at: datetime | None
    providers: tuple[ProviderKind, ...]


@dataclass(frozen=True)
class IngestionRunResult:
    provider: ProviderKind
    account_email: str
    checkpoint: IncrementalCheckpoint
    fetched_count: int
    normalized_count: int
    stored_count: int
    deduped_count: int
    trip_thread_count: int
    messages: tuple[NormalizedMailMessage, ...]
    trip_threads: tuple[TripConversationThread, ...]

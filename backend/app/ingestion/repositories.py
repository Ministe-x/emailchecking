from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.ingestion.models import NormalizedMailMessage
from app.providers.types import IncrementalCheckpoint, ProviderKind


@dataclass(frozen=True)
class CheckpointRow:
    provider: ProviderKind
    account_email: str
    cursor: str | None
    synced_until: datetime | None


class CheckpointRepository(Protocol):
    def get(self, provider: ProviderKind, account_email: str) -> IncrementalCheckpoint:
        ...

    def save(
        self, provider: ProviderKind, account_email: str, checkpoint: IncrementalCheckpoint
    ) -> None:
        ...


class MessageMetadataRepository(Protocol):
    def has_provider_message(
        self, provider: ProviderKind, account_email: str, provider_message_id: str
    ) -> bool:
        ...

    def has_dedup_key(self, account_email: str, dedup_key: str) -> bool:
        ...

    def store_batch(self, account_email: str, messages: tuple[NormalizedMailMessage, ...]) -> int:
        ...

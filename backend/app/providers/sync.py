from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from app.providers.types import IncrementalCheckpoint, RawMessageEnvelope


@dataclass(frozen=True)
class IncrementalSyncPlan:
    query_params: dict[str, str]
    page_token: str | None = None


@dataclass(frozen=True)
class IncrementalSyncResult:
    messages: tuple[RawMessageEnvelope, ...]
    next_checkpoint: IncrementalCheckpoint
    next_page_token: str | None = None
    has_more: bool = False


class IncrementalSyncStrategy(Protocol):
    """Provider-specific strategy that turns checkpoints into API query plans."""

    def build_plan(self, checkpoint: IncrementalCheckpoint) -> IncrementalSyncPlan:
        ...

    def derive_checkpoint(
        self,
        previous: IncrementalCheckpoint,
        page_messages: Iterable[RawMessageEnvelope],
    ) -> IncrementalCheckpoint:
        ...


class TimestampSyncStrategy:
    """Default strategy for providers that support updated-after style queries."""

    def __init__(self, updated_after_param: str = "updated_after") -> None:
        self._updated_after_param = updated_after_param

    def build_plan(self, checkpoint: IncrementalCheckpoint) -> IncrementalSyncPlan:
        query_params: dict[str, str] = {}
        if checkpoint.synced_until:
            query_params[self._updated_after_param] = checkpoint.synced_until.isoformat()
        return IncrementalSyncPlan(query_params=query_params)

    def derive_checkpoint(
        self,
        previous: IncrementalCheckpoint,
        page_messages: Iterable[RawMessageEnvelope],
    ) -> IncrementalCheckpoint:
        latest = previous.synced_until
        for message in page_messages:
            if message.internal_date and (latest is None or message.internal_date > latest):
                latest = message.internal_date
        return IncrementalCheckpoint(cursor=previous.cursor, synced_until=latest)

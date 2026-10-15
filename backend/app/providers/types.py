from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class ProviderKind(str, Enum):
    GMAIL = "gmail"
    SCHOOL = "school"


@dataclass(frozen=True)
class OAuthTokenSet:
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    scope: tuple[str, ...] = ()


@dataclass(frozen=True)
class MailboxIdentity:
    account_id: str
    email: str
    provider: ProviderKind


@dataclass(frozen=True)
class IncrementalCheckpoint:
    cursor: str | None = None
    synced_until: datetime | None = None


@dataclass(frozen=True)
class RawMessageEnvelope:
    provider_message_id: str
    thread_id: str | None
    internal_date: datetime | None
    payload: dict[str, Any]

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from app.providers.sync import IncrementalSyncResult, IncrementalSyncStrategy
from app.providers.types import IncrementalCheckpoint, MailboxIdentity, OAuthTokenSet, ProviderKind


class OAuthTokenRefresher(Protocol):
    def refresh(self, token_set: OAuthTokenSet) -> OAuthTokenSet:
        ...


class MailboxProvider(ABC):
    provider_kind: ProviderKind
    default_scopes: tuple[str, ...]
    sync_strategy: IncrementalSyncStrategy

    @abstractmethod
    def authorization_url(self, state: str) -> str:
        """Build provider-specific OAuth authorization URL."""

    @abstractmethod
    def exchange_code(self, code: str) -> OAuthTokenSet:
        """Exchange OAuth authorization code for token set."""

    @abstractmethod
    def refresh_tokens(self, token_set: OAuthTokenSet) -> OAuthTokenSet:
        """Refresh tokens; must avoid logging token material."""

    @abstractmethod
    def resolve_identity(self, token_set: OAuthTokenSet) -> MailboxIdentity:
        """Resolve account identity after auth."""

    @abstractmethod
    def incremental_sync(
        self,
        token_set: OAuthTokenSet,
        checkpoint: IncrementalCheckpoint,
        page_token: str | None = None,
    ) -> IncrementalSyncResult:
        """Fetch one page of messages and return sync continuation metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.providers.types import OAuthTokenSet, ProviderKind


@dataclass(frozen=True)
class TokenRecordKey:
    account_id: str
    provider: ProviderKind


class TokenStore(Protocol):
    """Token persistence. Real implementations must encrypt refresh tokens at rest."""

    def put(self, key: TokenRecordKey, token_set: OAuthTokenSet) -> None:
        ...

    def get(self, key: TokenRecordKey) -> OAuthTokenSet | None:
        ...

    def delete(self, key: TokenRecordKey) -> None:
        ...


class InMemoryTokenStore:
    """Unencrypted, process-local store. Only meant for tests."""

    def __init__(self) -> None:
        self._data: dict[TokenRecordKey, OAuthTokenSet] = {}

    def put(self, key: TokenRecordKey, token_set: OAuthTokenSet) -> None:
        if not token_set.access_token.strip():
            raise ValueError("access_token must not be empty")
        self._data[key] = token_set

    def get(self, key: TokenRecordKey) -> OAuthTokenSet | None:
        return self._data.get(key)

    def delete(self, key: TokenRecordKey) -> None:
        self._data.pop(key, None)

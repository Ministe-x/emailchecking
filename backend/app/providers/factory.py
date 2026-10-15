from __future__ import annotations

from dataclasses import dataclass

from app.config import AppConfig
from app.providers.base import MailboxProvider
from app.providers.gmail import GmailProvider
from app.providers.school import SchoolMailboxProvider
from app.providers.types import ProviderKind


class ProviderRegistrationError(RuntimeError):
    pass


@dataclass
class ProviderRegistry:
    _providers: dict[ProviderKind, MailboxProvider]

    @classmethod
    def from_config(cls, config: AppConfig) -> "ProviderRegistry":
        registry = cls(_providers={})
        registry.register(GmailProvider(config.gmail))
        registry.register(SchoolMailboxProvider(config.school))
        return registry

    def register(self, provider: MailboxProvider) -> None:
        if provider.provider_kind in self._providers:
            raise ProviderRegistrationError(
                f"Duplicate provider registration: {provider.provider_kind.value}"
            )
        self._providers[provider.provider_kind] = provider

    def get(self, provider_kind: ProviderKind) -> MailboxProvider:
        try:
            return self._providers[provider_kind]
        except KeyError as exc:
            raise ProviderRegistrationError(
                f"Provider not registered: {provider_kind.value}"
            ) from exc

    def supported_kinds(self) -> tuple[ProviderKind, ...]:
        return tuple(self._providers.keys())

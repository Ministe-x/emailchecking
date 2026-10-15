from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from urllib.parse import urlencode

from app.config import SchoolOAuthConfig
from app.providers.base import MailboxProvider
from app.providers.sync import IncrementalSyncResult, TimestampSyncStrategy
from app.providers.types import (
    IncrementalCheckpoint,
    MailboxIdentity,
    OAuthTokenSet,
    ProviderKind,
    RawMessageEnvelope,
)
from app.security.redaction import safe_token_debug

LOGGER = logging.getLogger(__name__)


class SchoolMailboxProvider(MailboxProvider):
    provider_kind = ProviderKind.SCHOOL
    default_scopes = ("openid", "email", "profile", "mail.read")

    def __init__(
        self, config: SchoolOAuthConfig, client: "SchoolMailboxApiClient | None" = None
    ) -> None:
        self._config = config
        self._client = client or StubSchoolMailboxApiClient(config.provider_type)
        self.sync_strategy = TimestampSyncStrategy(updated_after_param="updated_after")

    def authorization_url(self, state: str) -> str:
        if self._config.provider_type == "microsoft":
            return self._microsoft_authorize_url(state)
        if self._config.provider_type == "google_workspace":
            return self._google_authorize_url(state)
        raise ValueError(
            f"SCHOOL_PROVIDER_TYPE must be 'microsoft' or 'google_workspace', "
            f"got {self._config.provider_type!r}"
        )

    def exchange_code(self, code: str) -> OAuthTokenSet:
        # TODO: token endpoint (Entra ID or Google, depending on provider_type).
        return OAuthTokenSet(
            access_token=f"school_access_{code}",
            refresh_token=f"school_refresh_{code}",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scope=self.default_scopes,
        )

    def refresh_tokens(self, token_set: OAuthTokenSet) -> OAuthTokenSet:
        # TODO: same as GmailProvider.refresh_tokens. Entra ID rotates refresh
        # tokens on every use, so the new one must always be persisted.
        refreshed_access_token = f"{token_set.access_token}_refreshed"
        refreshed = OAuthTokenSet(
            access_token=refreshed_access_token,
            refresh_token=token_set.refresh_token,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scope=token_set.scope or self.default_scopes,
        )
        LOGGER.info("school.tokens_refreshed meta=%s", safe_token_debug(refreshed))
        return refreshed

    def resolve_identity(self, token_set: OAuthTokenSet) -> MailboxIdentity:
        # TODO: Graph /me or Google userinfo.
        return MailboxIdentity(
            account_id="school-account-placeholder",
            email="student@school.edu",
            provider=self.provider_kind,
        )

    def incremental_sync(
        self,
        token_set: OAuthTokenSet,
        checkpoint: IncrementalCheckpoint,
        page_token: str | None = None,
    ) -> IncrementalSyncResult:
        plan = self.sync_strategy.build_plan(checkpoint)
        page = self._client.fetch_messages(plan.query_params, page_token=page_token)
        messages = tuple(_adapt_school_message(message) for message in page.messages)
        derived = self.sync_strategy.derive_checkpoint(checkpoint, messages)
        next_checkpoint = IncrementalCheckpoint(
            cursor=page.next_page_token,
            synced_until=derived.synced_until,
        )
        return IncrementalSyncResult(
            messages=messages,
            next_checkpoint=next_checkpoint,
            next_page_token=page.next_page_token,
            has_more=page.next_page_token is not None,
        )

    def _microsoft_authorize_url(self, state: str) -> str:
        tenant = self._config.tenant_id or "common"
        query = urlencode(
            {
                "client_id": self._config.client_id,
                "response_type": "code",
                "redirect_uri": self._config.redirect_uri,
                "response_mode": "query",
                "scope": "offline_access Mail.Read User.Read",
                "state": state,
            }
        )
        return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize?{query}"

    def _google_authorize_url(self, state: str) -> str:
        query = urlencode(
            {
                "client_id": self._config.client_id,
                "redirect_uri": self._config.redirect_uri,
                "response_type": "code",
                "scope": " ".join(self.default_scopes),
                "access_type": "offline",
                "prompt": "consent",
                "state": state,
            }
        )
        return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"


@dataclass(frozen=True)
class SchoolRawMessage:
    id: str
    thread_id: str | None
    sent_at: datetime | None
    subject: str
    from_address: str
    to_addresses: tuple[str, ...]
    plain_body: str
    labels: tuple[str, ...]
    internet_message_id: str | None


@dataclass(frozen=True)
class SchoolMessagePage:
    messages: tuple[SchoolRawMessage, ...]
    next_page_token: str | None


class SchoolMailboxApiClient(Protocol):
    def fetch_messages(
        self, query_params: dict[str, str], page_token: str | None
    ) -> SchoolMessagePage:
        ...


class StubSchoolMailboxApiClient:
    """Fixed school mailbox page. Label casing follows the configured provider type."""

    def __init__(self, provider_type: str) -> None:
        self._provider_type = provider_type
        self._pages = self._build_pages(provider_type)

    def fetch_messages(
        self, query_params: dict[str, str], page_token: str | None
    ) -> SchoolMessagePage:
        return self._pages.get(page_token, SchoolMessagePage(messages=(), next_page_token=None))

    def _build_pages(self, provider_type: str) -> dict[str | None, SchoolMessagePage]:
        base_labels = (
            ("inbox", "focused")
            if provider_type == "microsoft"
            else ("INBOX", "CATEGORY_PERSONAL")
        )
        return {
            None: SchoolMessagePage(
                messages=(
                    SchoolRawMessage(
                        id="school-001",
                        thread_id="school-thread-conference",
                        sent_at=datetime(2026, 10, 1, 7, 50, tzinfo=timezone.utc),
                        subject="Conference travel booking confirmation",
                        from_address="travel-office@school.edu",
                        to_addresses=("student@school.edu",),
                        plain_body="Hotel reservation is booked near conference center.",
                        labels=base_labels,
                        internet_message_id="<conference-001@school.edu>",
                    ),
                    SchoolRawMessage(
                        id="school-002",
                        thread_id="school-thread-admin",
                        sent_at=datetime(2026, 10, 1, 8, 30, tzinfo=timezone.utc),
                        subject="Campus newsletter",
                        from_address="newsletter@school.edu",
                        to_addresses=("student@school.edu",),
                        plain_body="Weekly school highlights.",
                        labels=base_labels,
                        internet_message_id="<newsletter-001@school.edu>",
                    ),
                ),
                next_page_token=None,
            )
        }


def _adapt_school_message(message: SchoolRawMessage) -> RawMessageEnvelope:
    payload = {
        "message_id": message.id,
        "thread_id": message.thread_id,
        "subject": message.subject,
        "from": message.from_address,
        "to": list(message.to_addresses),
        "sent_at": message.sent_at.isoformat() if message.sent_at else None,
        "plain_body": message.plain_body,
        "labels": list(message.labels),
        "internet_message_id": message.internet_message_id,
    }
    return RawMessageEnvelope(
        provider_message_id=message.id,
        thread_id=message.thread_id,
        internal_date=message.sent_at,
        payload=payload,
    )

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from urllib.parse import urlencode

from app.config import OAuthProviderConfig
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


class GmailProvider(MailboxProvider):
    provider_kind = ProviderKind.GMAIL
    default_scopes = (
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/gmail.readonly",
    )

    def __init__(self, config: OAuthProviderConfig, client: "GmailApiClient | None" = None) -> None:
        self._config = config
        self._client = client or StubGmailApiClient()
        self.sync_strategy = TimestampSyncStrategy(updated_after_param="q_after")

    def authorization_url(self, state: str) -> str:
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

    def exchange_code(self, code: str) -> OAuthTokenSet:
        # TODO: POST https://oauth2.googleapis.com/token
        return OAuthTokenSet(
            access_token=f"gmail_access_{code}",
            refresh_token=f"gmail_refresh_{code}",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scope=self.default_scopes,
        )

    def refresh_tokens(self, token_set: OAuthTokenSet) -> OAuthTokenSet:
        # TODO: call the token endpoint. The refresh token should be read from the
        # encrypted TokenStore, and written back if Google rotates it.
        refreshed_access_token = f"{token_set.access_token}_refreshed"
        refreshed = OAuthTokenSet(
            access_token=refreshed_access_token,
            refresh_token=token_set.refresh_token,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scope=token_set.scope or self.default_scopes,
        )
        LOGGER.info("gmail.tokens_refreshed meta=%s", safe_token_debug(refreshed))
        return refreshed

    def resolve_identity(self, token_set: OAuthTokenSet) -> MailboxIdentity:
        # TODO: users.getProfile / userinfo lookup.
        return MailboxIdentity(
            account_id="gmail-account-placeholder",
            email="placeholder@gmail.com",
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
        messages = tuple(_adapt_gmail_message(item) for item in page.messages)
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


@dataclass(frozen=True)
class GmailRawMessage:
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
class GmailMessagePage:
    messages: tuple[GmailRawMessage, ...]
    next_page_token: str | None


class GmailApiClient(Protocol):
    def fetch_messages(
        self, query_params: dict[str, str], page_token: str | None
    ) -> GmailMessagePage:
        ...


class StubGmailApiClient:
    """Two fixed pages of Gmail messages so the pipeline can run offline."""

    def __init__(self) -> None:
        self._pages = {
            None: GmailMessagePage(
                messages=(
                    GmailRawMessage(
                        id="gmail-001",
                        thread_id="gmail-thread-flight-nyc",
                        sent_at=datetime(2026, 10, 1, 8, 15, tzinfo=timezone.utc),
                        subject="Flight itinerary to NYC",
                        from_address="alerts@airline.example",
                        to_addresses=("traveler@gmail.com",),
                        plain_body="Your flight booking is confirmed for Oct 22.",
                        labels=("INBOX", "CATEGORY_UPDATES"),
                        internet_message_id="<flight-nyc-001@example>",
                    ),
                    GmailRawMessage(
                        id="gmail-002",
                        thread_id="gmail-thread-promotions",
                        sent_at=datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc),
                        subject="Weekend sale on backpacks",
                        from_address="promo@store.example",
                        to_addresses=("traveler@gmail.com",),
                        plain_body="Save 30 percent this weekend.",
                        labels=("INBOX", "CATEGORY_PROMOTIONS"),
                        internet_message_id="<sale-002@example>",
                    ),
                ),
                next_page_token="page-2",
            ),
            "page-2": GmailMessagePage(
                messages=(
                    GmailRawMessage(
                        id="gmail-003",
                        thread_id="gmail-thread-flight-nyc",
                        sent_at=datetime(2026, 10, 2, 10, 30, tzinfo=timezone.utc),
                        subject="Re: Flight itinerary to NYC",
                        from_address="traveler@gmail.com",
                        to_addresses=("support@airline.example",),
                        plain_body="Can I update my seat?",
                        labels=("SENT",),
                        internet_message_id="<flight-nyc-003@example>",
                    ),
                ),
                next_page_token=None,
            ),
        }

    def fetch_messages(
        self, query_params: dict[str, str], page_token: str | None
    ) -> GmailMessagePage:
        return self._pages.get(page_token, GmailMessagePage(messages=(), next_page_token=None))


def _adapt_gmail_message(message: GmailRawMessage) -> RawMessageEnvelope:
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

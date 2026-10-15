from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from app.ingestion.models import NormalizedMailMessage
from app.providers.types import ProviderKind, RawMessageEnvelope

_SUBJECT_PREFIX_RE = re.compile(r"^\s*((re|fw|fwd)\s*:\s*)+", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_envelope(
    provider: ProviderKind, envelope: RawMessageEnvelope
) -> NormalizedMailMessage:
    payload = envelope.payload
    message_id = _first_non_empty(
        str(payload.get("message_id", "")).strip(),
        envelope.provider_message_id,
    )
    subject = str(payload.get("subject", "")).strip()
    from_address = str(payload.get("from", "")).strip().lower()
    to_addresses = _normalize_recipients(payload.get("to"))
    sent_at = _parse_datetime(payload.get("sent_at")) or envelope.internal_date
    plain_body = _to_text(payload.get("plain_body", ""))
    labels = tuple(
        str(label).strip().lower() for label in payload.get("labels", []) if str(label).strip()
    )
    provider_thread_id = (
        _none_if_empty(str(payload.get("thread_id", "")).strip()) or envelope.thread_id
    )
    conversation_key = build_conversation_key(
        subject=subject, provider_thread_id=provider_thread_id
    )
    dedup_key = build_dedup_key(
        internet_message_id=_none_if_empty(str(payload.get("internet_message_id", "")).strip()),
        from_address=from_address,
        to_addresses=to_addresses,
        subject=subject,
        sent_at=sent_at,
        plain_body=plain_body,
    )
    return NormalizedMailMessage(
        message_id=message_id,
        subject=subject,
        from_address=from_address,
        to_addresses=to_addresses,
        sent_at=sent_at,
        plain_body=plain_body,
        labels=labels,
        provider=provider,
        provider_thread_id=provider_thread_id,
        conversation_key=conversation_key,
        dedup_key=dedup_key,
        raw_payload=payload,
    )


def build_conversation_key(subject: str, provider_thread_id: str | None) -> str:
    if provider_thread_id:
        return f"thread:{provider_thread_id}"
    canonical = _canonical_subject(subject)
    return f"subject:{canonical}" if canonical else "subject:unknown"


def build_dedup_key(
    *,
    internet_message_id: str | None,
    from_address: str,
    to_addresses: tuple[str, ...],
    subject: str,
    sent_at: datetime | None,
    plain_body: str,
) -> str:
    # A message delivered to both mailboxes (e.g. cc'd to the school address) keeps the
    # same RFC 822 Message-ID, so it wins over the content hash whenever it is present.
    if internet_message_id:
        normalized_message_id = internet_message_id.strip().lower()
        return f"rfc822:{normalized_message_id}"

    sent_at_key = ""
    if sent_at:
        # Providers report delivery time with different precision; compare to the minute.
        sent_at_key = sent_at.astimezone(timezone.utc).replace(second=0, microsecond=0).isoformat()
    stable_input = "|".join(
        [
            from_address.strip().lower(),
            ",".join(sorted(address.lower() for address in to_addresses)),
            _canonical_subject(subject),
            sent_at_key,
            _body_fingerprint(plain_body),
        ]
    )
    digest = hashlib.sha256(stable_input.encode("utf-8")).hexdigest()
    return f"content:{digest}"


def _canonical_subject(subject: str) -> str:
    without_prefix = _SUBJECT_PREFIX_RE.sub("", subject or "")
    collapsed = _WHITESPACE_RE.sub(" ", without_prefix).strip().lower()
    return collapsed


def _normalize_recipients(raw: object) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        candidates = [item.strip() for item in raw.split(",")]
    elif isinstance(raw, (list, tuple, set)):
        candidates = [str(item).strip() for item in raw]
    else:
        return ()
    return tuple(item.lower() for item in candidates if item)


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            return parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return None


def _body_fingerprint(plain_body: str) -> str:
    normalized_body = _WHITESPACE_RE.sub(" ", plain_body).strip().lower()
    return normalized_body[:200]


def _to_text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _none_if_empty(value: str) -> str | None:
    return value if value else None


def _first_non_empty(*values: str) -> str:
    for value in values:
        if value:
            return value
    return ""

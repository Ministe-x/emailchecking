from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone

from app.calendar.models import CalendarCandidate, TripEvent

_ISO_DATETIME_RE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?)\b"
)
_DATE_TIME_RE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}):(\d{2}))?(?:\s*(UTC|GMT|[+-]\d{2}:\d{2}))?\b",
    re.IGNORECASE,
)
_BOOKING_REF_RE = re.compile(
    r"(?:booking|reservation|reference|ref|pnr)\s*(?:#|:|-)?\s*([A-Za-z0-9-]{4,})",
    re.IGNORECASE,
)
_EXPLICIT_LOCATION_RE = re.compile(
    r"(?:location|venue)\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9,\-./ ]{2,80})",
    re.IGNORECASE,
)
_CONTEXT_LOCATION_RE = re.compile(
    r"\b(?:at|in)\s+([A-Z][A-Za-z0-9,\-./ ]{2,60})",
    re.IGNORECASE,
)


def extract_event(candidate: CalendarCandidate) -> TripEvent:
    combined_text = f"{candidate.subject}\n{candidate.plain_body}"
    start_at, end_at, parsed_explicit_end = _extract_interval(
        combined_text,
        fallback_start=candidate.sent_at or datetime.now(timezone.utc),
    )
    timezone_name = _timezone_name(start_at)
    location = _extract_location(combined_text)
    booking_ref = _extract_booking_ref(combined_text)
    confidence = _score_confidence(
        candidate=candidate,
        has_explicit_time=(candidate.sent_at is not None and start_at != candidate.sent_at)
        or _has_datetime_token(combined_text),
        has_explicit_end=parsed_explicit_end,
        has_location=location is not None,
        has_booking_ref=booking_ref is not None,
    )
    event_id = _build_event_id(
        message_identity=candidate.message_identity,
        start_at=start_at,
        title=candidate.subject,
        booking_ref=booking_ref,
    )
    return TripEvent(
        account_email=candidate.account_email,
        event_id=event_id,
        message_identity=candidate.message_identity,
        title=candidate.subject or f"{candidate.trip_type.title()} itinerary",
        start_at=start_at,
        end_at=end_at,
        timezone=timezone_name,
        location=location,
        booking_ref=booking_ref,
        source_email=candidate.source_email,
        priority_score=candidate.priority_score,
        confidence=confidence,
        trip_type=candidate.trip_type,
    )


def rank_events(events: tuple[TripEvent, ...]) -> tuple[TripEvent, ...]:
    return tuple(
        sorted(
            events,
            key=lambda event: (
                -event.priority_score,
                event.start_at,
                -event.confidence,
                event.title.lower(),
            ),
        )
    )


def _extract_interval(text: str, *, fallback_start: datetime) -> tuple[datetime, datetime, bool]:
    datetimes = _extract_datetimes(text)
    if len(datetimes) >= 2:
        start_at = datetimes[0]
        end_at = datetimes[1]
        if end_at <= start_at:
            end_at = start_at + timedelta(hours=1)
        return start_at, end_at, True
    if len(datetimes) == 1:
        start_at = datetimes[0]
        return start_at, start_at + timedelta(hours=1), False

    start_at = _ensure_tz(fallback_start)
    return start_at, start_at + timedelta(hours=1), False


def _extract_datetimes(text: str) -> tuple[datetime, ...]:
    values: list[datetime] = []
    for match in _ISO_DATETIME_RE.findall(text):
        parsed = _parse_iso_datetime(match)
        if parsed is not None:
            values.append(parsed)

    for date_text, hour_text, minute_text, tz_text in _DATE_TIME_RE.findall(text):
        if _text_in_iso_token(text, date_text):
            continue
        try:
            base = datetime.fromisoformat(date_text)
        except ValueError:
            continue
        hour = int(hour_text) if hour_text else 9
        minute = int(minute_text) if minute_text else 0
        base = base.replace(hour=hour, minute=minute)
        values.append(_apply_timezone(base, tz_text))

    return tuple(sorted(_ensure_tz(value) for value in values))


def _parse_iso_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _apply_timezone(value: datetime, tz_text: str) -> datetime:
    if not tz_text:
        return value.replace(tzinfo=timezone.utc)
    upper = tz_text.upper()
    if upper in {"UTC", "GMT"}:
        return value.replace(tzinfo=timezone.utc)
    sign = 1 if tz_text.startswith("+") else -1
    try:
        hours, minutes = tz_text[1:].split(":")
        delta = timedelta(hours=int(hours), minutes=int(minutes))
    except (ValueError, IndexError):
        return value.replace(tzinfo=timezone.utc)
    return value.replace(tzinfo=timezone(sign * delta))


def _timezone_name(value: datetime) -> str:
    offset = value.utcoffset()
    if offset is None:
        return "UTC"
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    absolute = abs(total_minutes)
    hours = absolute // 60
    minutes = absolute % 60
    return f"UTC{sign}{hours:02d}:{minutes:02d}"


def _extract_booking_ref(text: str) -> str | None:
    match = _BOOKING_REF_RE.search(text)
    if not match:
        return None
    return match.group(1).strip().upper()


def _extract_location(text: str) -> str | None:
    explicit = _EXPLICIT_LOCATION_RE.search(text)
    if explicit:
        value = re.sub(r"\s+", " ", explicit.group(1)).strip(" ,.-")
        return value or None

    contextual = _CONTEXT_LOCATION_RE.search(text)
    if not contextual:
        return None
    value = re.sub(r"\s+", " ", contextual.group(1)).strip(" ,.-")
    return value or None


def _score_confidence(
    *,
    candidate: CalendarCandidate,
    has_explicit_time: bool,
    has_explicit_end: bool,
    has_location: bool,
    has_booking_ref: bool,
) -> float:
    score = 0.45
    if candidate.trip_type not in {"none", "other"}:
        score += 0.15
    if has_explicit_time:
        score += 0.2
    if has_explicit_end:
        score += 0.05
    if has_location:
        score += 0.1
    if has_booking_ref:
        score += 0.1
    # Candidates are already non-ads, so a confident "not an ad" verdict nudges the score a bit.
    score += max(0.0, min(0.05, candidate.ad_confidence * 0.05))
    return round(max(0.0, min(1.0, score)), 4)


def _build_event_id(
    *, message_identity: str, start_at: datetime, title: str, booking_ref: str | None
) -> str:
    basis = "|".join(
        (
            message_identity,
            start_at.isoformat(),
            title.strip().lower(),
            booking_ref or "",
        )
    )
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:20]
    return f"evt_{digest}"


def _ensure_tz(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _text_in_iso_token(text: str, date_text: str) -> bool:
    return bool(re.search(rf"{re.escape(date_text)}T\d{{2}}:\d{{2}}", text))


def _has_datetime_token(text: str) -> bool:
    return bool(_ISO_DATETIME_RE.search(text) or _DATE_TIME_RE.search(text))

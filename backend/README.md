# Backend

Python service that pulls mail from a Gmail account and a school mailbox, decides which
messages are about travel, and turns those into calendar events for the Apple client.

It has no third-party runtime dependencies (standard library + SQLite). The provider API
clients and the classification model are both stubbed for now, so everything below runs
offline.

## How it fits together

```
providers/   OAuth URLs, token handling, paged incremental fetch (Gmail, school mailbox)
ingestion/   normalize -> dedup -> group into trip threads -> store metadata + checkpoint
ai/          ad filter -> trip relevance -> importance, each validated against a schema
calendar/    extract time/location/booking ref -> detect conflicts -> ranked timeline
privacy/     delete all rows for one account
security/    token fingerprints for logs, TokenStore interface
```

All stages share one SQLite file. Each stage reads what the previous one stored, so the
calendar step can be rebuilt without classifying the messages again.

### Ingestion

Every provider message is mapped to the same shape (`messageId, subject, from, to, sentAt,
plainBody, labels, provider`). Duplicates are dropped in two passes:

1. same provider + provider message ID (re-fetching a page we've already seen), and
2. same dedup key across providers. The key is the RFC 822 `Message-ID` if there is one,
   otherwise a SHA-256 over sender, sorted recipients, subject without `Re:`/`Fwd:`,
   send time rounded to the minute, and the first 200 characters of the body.

The second case matters because a lot of university travel mail is cc'd to both a
personal and a school address.

Sync is checkpoint based. `TimestampSyncStrategy` turns the stored `synced_until` value
into an "updated after" query parameter and advances it to the newest message seen.

### Classification

Three stages run in order, and the later ones get the earlier outputs as context:

| stage            | output fields                    |
| ---------------- | -------------------------------- |
| `ad_filter`      | `isAd`, `reason`, `confidence`   |
| `trip_relevance` | `isTripRelated`, `tripType`      |
| `importance`     | `priorityScore`, `importanceReason` |

Model output is never trusted directly. `ai/schema.py` checks types, ranges, and that
`tripType` is `none` whenever `isTripRelated` is false. If validation fails or the model
is unreachable, the stage is tried again (up to `AI_MODEL_MAX_RETRIES` attempts in total)
and then falls back to the keyword rules in `ai/rules.py`. Every stored row records the model
name/version, attempt count and whether the fallback was used, which makes it possible
to see how often the model actually gets used.

The only provider implemented right now is `stub`, which wraps those same rules.

### Calendar

For messages that are trip related and not ads, `calendar/extractor.py` pulls out
start/end times (ISO 8601 or `YYYY-MM-DD HH:MM` with an optional offset), a location and
a booking reference with regexes. If no time is found it uses the send time and lowers
the confidence score. Two kinds of conflict are flagged: overlapping time ranges and the
same booking reference showing up on more than one event.

The timeline is sorted by priority first and then start time.

## Setup

Python 3.10+ is the target (the code also runs on 3.9 thanks to
`from __future__ import annotations`).

```bash
cd backend
cp .env.example .env    # then fill in real values
set -a; source .env; set +a
```

`load_config()` reads plain environment variables. Nothing loads `.env` for you.

| variable | notes |
| --- | --- |
| `APP_ENV` | `local`, `dev` or `prod` |
| `ENCRYPTION_KEY_REF` | key ID in your KMS / secret manager, not the key itself |
| `OAUTH_STATE_SIGNING_SECRET` | signs the OAuth `state` parameter |
| `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REDIRECT_URI` | Google Cloud OAuth client |
| `SCHOOL_PROVIDER_TYPE` | `microsoft` (Graph) or `google_workspace` |
| `SCHOOL_CLIENT_ID`, `SCHOOL_CLIENT_SECRET`, `SCHOOL_REDIRECT_URI` | app registration for the school tenant |
| `SCHOOL_TENANT_ID` | Entra ID tenant; falls back to `common` |
| `AI_MODEL_PROVIDER` | only `stub` for now |
| `AI_MODEL_NAME`, `AI_MODEL_VERSION` | stored next to each output |
| `AI_MODEL_MAX_RETRIES` | attempts per stage before the rule fallback, default 2 |

Redirect URIs have to match what is registered in the Google Cloud console / Entra
portal exactly. Use a separate registration per environment so production never accepts
a `localhost` callback.

## Running the pipeline

```python
from app.ai.bootstrap import build_ai_pipeline_service
from app.calendar.bootstrap import build_calendar_timeline_service
from app.config import load_config
from app.ingestion.bootstrap import build_ingestion_service
from app.main import bootstrap_registry
from app.providers.types import OAuthTokenSet, ProviderKind

DB = "./data/ingestion.sqlite3"
account = "user@example.com"

ingestion = build_ingestion_service(bootstrap_registry(), db_path=DB)
ai = build_ai_pipeline_service(db_path=DB, config=load_config().ai_model)
calendar = build_calendar_timeline_service(db_path=DB)

run = ingestion.run_incremental_sync(
    provider=ProviderKind.GMAIL,
    account_email=account,
    token_set=OAuthTokenSet(access_token="x", refresh_token="y", expires_at=None),
)
ai.process_messages(account_email=account, messages=run.messages)
calendar.refresh_account(account_email=account)

payload = calendar.get_upcoming_timeline_payload(account_email=account, limit=30)
```

Running the sync a second time stores nothing new, because the checkpoint and the
dedup keys already cover those messages.

Each event in `payload["events"]` has `eventId, title, start, end, timezone, location,
bookingRef, sourceEmail, priorityScore, confidence, tripType`. The Apple client README
documents the full response shape.

## Deleting an account

```python
from app.ingestion.sqlite_repositories import SQLiteConnectionFactory
from app.privacy.service import AccountDataDeletionService

report = AccountDataDeletionService(SQLiteConnectionFactory(DB)).delete_account_data(account)
print(report.deleted_rows)
```

This clears `sync_checkpoints`, `raw_message_metadata`, `ai_stage_outputs`, `trip_events`
and `trip_conflicts` for that address.

## Handling tokens and mail content

- Access and refresh tokens are never logged. `security/redaction.py` logs a short
  SHA-256 fingerprint instead, which is enough to tell two tokens apart while debugging.
- Refresh tokens should only be persisted encrypted (`TokenStore`). `InMemoryTokenStore`
  is for tests.
- Pipeline logs contain counts and message IDs, never subjects or bodies.
- `exchange_code`, `refresh_tokens` and `resolve_identity` still return placeholder
  values. The real token endpoint calls are the next thing to implement.

## School mailbox modes

`microsoft` assumes Microsoft Graph semantics (`Mail.Read`, `offline_access`, lowercase
folder labels like `inbox`/`focused`). `google_workspace` assumes the Gmail API with
uppercase system labels. Offline, the stub pages only differ in label format, which is
enough to check that normalization lowercases both the same way.

## Tests

```bash
cd backend
python3 -m unittest discover -s tests -p "test_*.py"
```

Lint with `pip install -e '.[dev]'` followed by `ruff check app tests` (config in
`pyproject.toml`).

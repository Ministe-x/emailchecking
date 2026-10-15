from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class OAuthProviderConfig:
    client_id: str
    client_secret: str
    redirect_uri: str


@dataclass(frozen=True)
class SchoolOAuthConfig(OAuthProviderConfig):
    provider_type: str
    tenant_id: str | None = None


@dataclass(frozen=True)
class AppConfig:
    app_env: str
    encryption_key_ref: str
    oauth_state_signing_secret: str
    gmail: OAuthProviderConfig
    school: SchoolOAuthConfig
    ai_model: "AIModelConfig"


@dataclass(frozen=True)
class AIModelConfig:
    provider: str
    model_name: str
    model_version: str
    max_retries: int


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required env var: {name}")
    return value


def _int_with_default(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer; got {raw!r}") from exc
    if value < 1:
        raise ValueError(f"Environment variable {name} must be >= 1")
    return value


def load_config() -> AppConfig:
    return AppConfig(
        app_env=os.getenv("APP_ENV", "local"),
        encryption_key_ref=_required("ENCRYPTION_KEY_REF"),
        oauth_state_signing_secret=_required("OAUTH_STATE_SIGNING_SECRET"),
        gmail=OAuthProviderConfig(
            client_id=_required("GMAIL_CLIENT_ID"),
            client_secret=_required("GMAIL_CLIENT_SECRET"),
            redirect_uri=_required("GMAIL_REDIRECT_URI"),
        ),
        school=SchoolOAuthConfig(
            provider_type=_required("SCHOOL_PROVIDER_TYPE"),
            client_id=_required("SCHOOL_CLIENT_ID"),
            client_secret=_required("SCHOOL_CLIENT_SECRET"),
            redirect_uri=_required("SCHOOL_REDIRECT_URI"),
            tenant_id=os.getenv("SCHOOL_TENANT_ID"),
        ),
        ai_model=AIModelConfig(
            provider=os.getenv("AI_MODEL_PROVIDER", "stub").strip() or "stub",
            model_name=os.getenv("AI_MODEL_NAME", "deterministic-stub").strip()
            or "deterministic-stub",
            model_version=os.getenv("AI_MODEL_VERSION", "v1").strip() or "v1",
            max_retries=_int_with_default("AI_MODEL_MAX_RETRIES", 2),
        ),
    )

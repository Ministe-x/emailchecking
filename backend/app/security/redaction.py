from __future__ import annotations

import hashlib

from app.providers.types import OAuthTokenSet


def token_fingerprint(token: str | None) -> str:
    if not token:
        return "none"
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]
    return f"sha256:{digest}"


def safe_token_debug(token_set: OAuthTokenSet) -> dict[str, object]:
    """Return token metadata suitable for logs without exposing secret values."""
    return {
        "access_token_fp": token_fingerprint(token_set.access_token),
        "refresh_token_fp": token_fingerprint(token_set.refresh_token),
        "expires_at": token_set.expires_at.isoformat() if token_set.expires_at else None,
        "scope_count": len(token_set.scope),
    }

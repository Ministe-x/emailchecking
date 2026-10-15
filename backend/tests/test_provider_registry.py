from __future__ import annotations

import unittest

from app.config import AIModelConfig, AppConfig, OAuthProviderConfig, SchoolOAuthConfig
from app.providers.factory import ProviderRegistrationError, ProviderRegistry
from app.providers.gmail import GmailProvider
from app.providers.types import ProviderKind


def _test_config() -> AppConfig:
    return AppConfig(
        app_env="test",
        encryption_key_ref="kms/test/key",
        oauth_state_signing_secret="secret",
        gmail=OAuthProviderConfig(
            client_id="gmail-client",
            client_secret="gmail-secret",
            redirect_uri="http://localhost/callback/gmail",
        ),
        school=SchoolOAuthConfig(
            provider_type="microsoft",
            client_id="school-client",
            client_secret="school-secret",
            redirect_uri="http://localhost/callback/school",
            tenant_id="tenant",
        ),
        ai_model=AIModelConfig(
            provider="stub",
            model_name="deterministic-stub",
            model_version="v1",
            max_retries=2,
        ),
    )


class ProviderRegistryTest(unittest.TestCase):
    def test_registry_from_config_registers_gmail_and_school(self) -> None:
        registry = ProviderRegistry.from_config(_test_config())
        self.assertEqual(
            registry.supported_kinds(),
            (ProviderKind.GMAIL, ProviderKind.SCHOOL),
        )

    def test_duplicate_provider_registration_raises_error(self) -> None:
        registry = ProviderRegistry.from_config(_test_config())
        with self.assertRaises(ProviderRegistrationError):
            registry.register(GmailProvider(_test_config().gmail))

    def test_get_raises_for_missing_provider(self) -> None:
        registry = ProviderRegistry(_providers={})
        with self.assertRaises(ProviderRegistrationError):
            registry.get(ProviderKind.GMAIL)


if __name__ == "__main__":
    unittest.main()

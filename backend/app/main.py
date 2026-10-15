from __future__ import annotations

from app.config import load_config
from app.providers.factory import ProviderRegistry


def bootstrap_registry() -> ProviderRegistry:
    config = load_config()
    return ProviderRegistry.from_config(config)


if __name__ == "__main__":
    registry = bootstrap_registry()
    kinds = ", ".join(kind.value for kind in registry.supported_kinds())
    print(f"Configured mailbox providers: {kinds}")

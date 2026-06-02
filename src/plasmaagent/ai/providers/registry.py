from typing import Dict, Type
from plasmaagent.ai.providers.base import LLMProvider


_PROVIDER_REGISTRY: Dict[str, Type[LLMProvider]] = {}
_DEFAULT_PROVIDER = "rule_based"


def register_provider(name: str, provider_class: Type[LLMProvider]) -> None:
    _PROVIDER_REGISTRY[name] = provider_class


def get_provider(name: str | None = None) -> LLMProvider:
    provider_name = name or _DEFAULT_PROVIDER
    
    if provider_name not in _PROVIDER_REGISTRY:
        available = ", ".join(_PROVIDER_REGISTRY.keys())
        raise ValueError(
            f"Provider '{provider_name}' not found. Available: {available}"
        )
    
    provider_class = _PROVIDER_REGISTRY[provider_name]
    return provider_class()


def list_providers() -> list[str]:
    return list(_PROVIDER_REGISTRY.keys())


def set_default_provider(name: str) -> None:
    global _DEFAULT_PROVIDER
    if name not in _PROVIDER_REGISTRY:
        raise ValueError(f"Provider '{name}' not registered")
    _DEFAULT_PROVIDER = name

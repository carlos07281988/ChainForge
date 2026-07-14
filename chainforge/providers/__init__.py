"""Provider imports — lazy-loaded to avoid requiring all SDKs at package level."""
from __future__ import annotations

import importlib

_LAZY_REGISTRY: dict[str, str] = {
    "OpenAIProvider": "chainforge.providers.openai",
    "AnthropicProvider": "chainforge.providers.anthropic",
    "GoogleProvider": "chainforge.providers.google",
    "AzureProvider": "chainforge.providers.azure",
    "BedrockProvider": "chainforge.providers.bedrock",
}


def __getattr__(name: str):
    if name in _LAZY_REGISTRY:
        mod = importlib.import_module(_LAZY_REGISTRY[name])
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = list(_LAZY_REGISTRY.keys())

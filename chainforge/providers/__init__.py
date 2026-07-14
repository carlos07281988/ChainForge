# Copyright 2026 ChainForge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
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

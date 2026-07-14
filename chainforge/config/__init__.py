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
"""Agent Configuration — declare agents with YAML/JSON.

Allows defining ChainForge agents via declarative configuration files,
supporting environment variable injection and component auto-wiring.

Usage:
    from chainforge.config.loader import load_agent_config
    from chainforge.config.builder import build_agent_from_config

    config = load_agent_config("agent.yaml")
    agent = build_agent_from_config(config)
"""

from chainforge.config.schema import AgentConfig, LLMConfig, ToolConfig, MemoryConfig
from chainforge.config.loader import load_agent_config, load_agent_config_from_dict
from chainforge.config.builder import build_agent_from_config

__all__ = [
    "AgentConfig",
    "LLMConfig",
    "ToolConfig",
    "MemoryConfig",
    "load_agent_config",
    "load_agent_config_from_dict",
    "build_agent_from_config",
]

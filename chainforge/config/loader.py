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
"""Config loader — load AgentConfig from YAML/JSON files with env var injection."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from chainforge.config.schema import AgentConfig
from chainforge.logging import get_logger

logger = get_logger("config.loader")

_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _inject_env_vars(value: str) -> str:
    """Replace ${VAR_NAME} with environment variable values.

    Supports:
      - ${API_KEY} -> os.environ["API_KEY"]
      - ${API_KEY:-default} -> os.environ.get("API_KEY", "default")
    """

    def _replace(match: re.Match) -> str:
        var_expr = match.group(1)
        if ":-" in var_expr:
            var_name, default = var_expr.split(":-", 1)
            return os.environ.get(var_name, default)
        return os.environ[var_expr]

    return _ENV_VAR_PATTERN.sub(_replace, value)


def _resolve_env_vars(obj):
    """Recursively resolve ${VAR} patterns in strings within a structure."""
    if isinstance(obj, str):
        return _inject_env_vars(obj)
    elif isinstance(obj, dict):
        return {k: _resolve_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_resolve_env_vars(item) for item in obj]
    return obj


def load_agent_config(path: str | Path) -> AgentConfig:
    """Load agent configuration from a YAML or JSON file.

    Supports ${ENV_VAR} and ${ENV_VAR:-default} syntax in string values.

    Args:
        path: Path to config file (.yaml, .yml, or .json).

    Returns:
        Parsed AgentConfig with environment variables resolved.

    Raises:
        FileNotFoundError: Config file does not exist.
        ValueError: Unsupported file format or parse error.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw_text = path.read_text(encoding="utf-8")
    ext = path.suffix.lower()

    if ext in (".yaml", ".yml"):
        try:
            import yaml
            data = yaml.safe_load(raw_text)
        except ImportError:
            raise ImportError(
                "PyYAML is required for loading YAML config. "
                "Install: pip install pyyaml"
            )
        except yaml.YAMLError as e:
            raise ValueError(f"YAML parse error in {path}: {e}")
    elif ext == ".json":
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON parse error in {path}: {e}")
    else:
        raise ValueError(f"Unsupported config format: {ext} (supported: .yaml, .yml, .json)")

    # Resolve environment variables
    data = _resolve_env_vars(data)

    config = AgentConfig(**data)
    logger.info(f"Loaded agent config: {config.name} ({config.llm.provider}/{config.llm.model})")
    return config


def load_agent_config_from_dict(data: dict) -> AgentConfig:
    """Load agent configuration from a Python dict (with env var resolution).

    Args:
        data: Configuration dictionary.

    Returns:
        Parsed AgentConfig.
    """
    data = _resolve_env_vars(data)
    return AgentConfig(**data)

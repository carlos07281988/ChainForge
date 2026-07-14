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
"""ChainForge logging — structured, configurable, production-ready.

Usage:
    from chainforge import configure_logging

    # Quick start
    configure_logging(level="INFO")

    # JSON structured logging
    configure_logging(level="DEBUG", format="json")

    # Per-module levels
    configure_logging(
        level="WARNING",
        module_levels={"agent": "DEBUG", "providers": "INFO"},
    )
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

# Sentinel
_initialized = False

# Module name → logger cache
_loggers: dict[str, logging.Logger] = {}


class StructuredFormatter(logging.Formatter):
    """JSON-structured log formatter. Parses the extra data dict from log calls."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%H:%M:%S.%f")[:-3],
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if hasattr(record, "data") and record.data:
            entry["data"] = record.data
        if record.exc_info and record.exc_info[0]:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


_DEFAULT_TEXT_FORMAT = "[%(asctime)s] %(levelname)-7s %(name)s | %(message)s"
_DEFAULT_DATE_FORMAT = "%H:%M:%S"


def configure_logging(
    level: str = "INFO",
    format: str = "text",
    output: str = "console",
    module_levels: dict[str, str] | None = None,
) -> logging.Logger:
    """Configure ChainForge logging globally.

    Args:
        level: Default log level (DEBUG, INFO, WARNING, ERROR).
        format: ``"text"`` for human-readable, ``"json"`` for structured.
        output: ``"console"`` (stdout), ``"stderr"``, or a file path.
        module_levels: Per-module overrides, e.g. ``{"agent": "DEBUG"}``.
    """
    global _initialized
    root = logging.getLogger("chainforge")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove any existing handlers to avoid duplicates on re-config
    root.handlers.clear()

    # Handler
    out = output.lower()
    if out in ("console", "stdout"):
        handler: logging.Handler = logging.StreamHandler(sys.stdout)
    elif out == "stderr":
        handler = logging.StreamHandler(sys.stderr)
    else:
        handler = logging.FileHandler(output)

    # Formatter
    if format == "json":
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(logging.Formatter(_DEFAULT_TEXT_FORMAT, datefmt=_DEFAULT_DATE_FORMAT))

    root.addHandler(handler)

    # Per-module levels
    if module_levels:
        for mod, lvl in module_levels.items():
            logging.getLogger(f"chainforge.{mod}").setLevel(getattr(logging, lvl.upper(), logging.INFO))

    _initialized = True
    return root


def get_logger(name: str) -> logging.Logger:
    """Get a ChainForge module logger.

    The logger is namespaced under ``chainforge.<name>``.
    """
    if name not in _loggers:
        _loggers[name] = logging.getLogger(f"chainforge.{name}")
    return _loggers[name]


def log_data(logger: logging.Logger, level: int, msg: str, data: dict[str, Any] | None = None, **kwargs):
    """Log a message with structured data attached.

    The data dict will appear in JSON logs under ``"data"``.
    """
    extra = kwargs.pop("extra", {})
    if data:
        extra["data"] = data
    logger.log(level, msg, extra=extra, **kwargs)

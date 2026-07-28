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
"""Alert rules, channels, and engine for SOC integration."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from chainforge.logging import get_logger

logger = get_logger("enterprise.observe")


class AlertRule(BaseModel):
    """A rule defining when to trigger an alert."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = ""
    condition: str = ""
    severity: str = "medium"  # low | medium | high | critical
    message_template: str = ""
    cooldown_minutes: int = 30
    enabled: bool = True


class Alert(BaseModel):
    """A triggered alert."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    rule_name: str = ""
    severity: str = "medium"
    message: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)
    acknowledged: bool = False

    def to_json(self) -> dict:
        return self.model_dump()


class AlertChannel(BaseModel):
    """Where to send alerts."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    type: str = "stdout"  # stdout | webhook | slack | pagerduty | custom
    webhook_url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def slack(cls, webhook_url: str) -> "AlertChannel":
        return cls(type="slack", webhook_url=webhook_url)

    @classmethod
    def webhook(cls, url: str) -> "AlertChannel":
        return cls(type="webhook", webhook_url=url)

    @classmethod
    def pagerduty(cls, routing_key: str) -> "AlertChannel":
        return cls(type="pagerduty", webhook_url=routing_key)


class AlertEngine:
    """Evaluates alert rules against current metrics and generates Alerts."""

    def __init__(self, channels: list[AlertChannel] | None = None):
        self._rules: list[AlertRule] = []
        self._history: list[Alert] = []
        self._last_fire: dict[str, float] = {}
        self._channels = channels or [AlertChannel(type="stdout")]

    def add_rule(self, rule: AlertRule) -> None:
        self._rules.append(rule)

    def remove_rule(self, name: str) -> bool:
        cnt = len(self._rules)
        self._rules = [r for r in self._rules if r.name != name]
        return len(self._rules) < cnt

    def evaluate(
        self,
        metrics: dict,
        known_tools: set[str],
        baseline: dict | None = None,
    ) -> list[Alert]:
        """Evaluate all rules against current metrics. Returns triggered alerts."""
        alerts = []
        for rule in self._rules:
            if not rule.enabled:
                continue
            # Cooldown check
            last = self._last_fire.get(rule.name, 0)
            if time.time() - last < rule.cooldown_minutes * 60:
                continue
            triggered = self._check_condition(rule, metrics, known_tools, baseline)
            if triggered:
                self._last_fire[rule.name] = time.time()
                msg = rule.message_template
                for k, v in metrics.items():
                    msg = msg.replace("{" + k + "}", str(v))
                alert = Alert(
                    rule_name=rule.name,
                    severity=rule.severity,
                    message=msg,
                    metrics=metrics,
                )
                alerts.append(alert)
                self._history.append(alert)
                logger.info(
                    "Alert triggered: rule=%s severity=%s", rule.name, rule.severity
                )
        return alerts

    def _check_condition(
        self,
        rule: AlertRule,
        metrics: dict,
        known_tools: set[str],
        baseline: dict | None,
    ) -> bool:
        cond = rule.condition.lower()
        if "failure_rate" in cond and baseline:
            fr = metrics.get("failure_rate", 0)
            bl_fr = baseline.get("failure_rate", 0.01)
            if ">" in cond:
                try:
                    threshold = float(cond.split(">")[-1].strip())
                    return bl_fr > 0 and fr > bl_fr * threshold
                except (ValueError, IndexError):
                    pass
        if "new_tool" in cond.lower():
            tool_name = metrics.get("last_tool", "")
            return tool_name not in known_tools and tool_name != ""
        if "tokens" in cond and baseline:
            tpc = metrics.get("tokens_per_call", 0)
            bl_tpc = baseline.get("tokens_per_call", 1)
            return bl_tpc > 0 and tpc > bl_tpc * 2
        return False

    @property
    def recent_alerts(self, limit: int = 20) -> list[Alert]:
        return sorted(
            self._history, key=lambda a: a.timestamp, reverse=True
        )[:limit]

    @property
    def history(self) -> list[Alert]:
        return list(self._history)

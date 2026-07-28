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
"""Training data collection for agent distillation."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from chainforge.logging import get_logger

logger = get_logger("enterprise.distill")


class TrainingPair(BaseModel):
    """A single input-to-output training pair."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    instruction: str = ""
    input: str = ""
    output: str = ""
    model_used: str = ""
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    timestamp: float = Field(default_factory=time.time)
    tokens: int = 0
    cost: float = 0.0


class TrainingDataset(BaseModel):
    """Collected training data ready for distillation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = ""
    version: str = "1.0"
    format: str = "alpaca"
    pairs: list[TrainingPair] = Field(default_factory=list)
    total_pairs: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    created_at: float = Field(default_factory=time.time)

    def save(self, path: str) -> None:
        p = Path(path)
        if p.suffix == ".jsonl":
            p.write_text(
                "\n".join(
                    json.dumps(
                        {
                            "instruction": tp.instruction,
                            "input": tp.input,
                            "output": tp.output,
                        }
                    )
                    for tp in self.pairs
                ),
                encoding="utf-8",
            )
        else:
            p.write_text(
                json.dumps(self.model_dump(), indent=2, default=str),
                encoding="utf-8",
            )

    def to_json(self) -> dict:
        return self.model_dump()


class TrainingDataCollector:
    """Middleware that collects agent input-to-output pairs for distillation training.

    Usage:
        collector = TrainingDataCollector()
        agent = Agent(llm=gpt4o, middlewares=[collector.middleware()])
        # Run production traffic...
        dataset = collector.export(format="alpaca")
        dataset.save("distill_data.jsonl")
    """

    def __init__(self):
        self._pairs: list[TrainingPair] = []
        self._current_input: str = ""

    def middleware(self):
        async def _mw(messages, ctx, next_handler):
            if messages:
                last = messages[-1]
                self._current_input = (
                    str(last.content)
                    if hasattr(last, "content")
                    else str(last)
                )
            output_parts: list[str] = []
            model = ""
            tokens = 0
            cost = 0.0
            async for event in next_handler(messages, ctx):
                if hasattr(event, "content") and event.content:
                    output_parts.append(str(event.content))
                    model = getattr(event, "model", model)
                if hasattr(event, "usage") and event.usage:
                    tokens = event.usage.get("total_tokens", 0)
                    cost = getattr(event, "cost", 0.0) or 0.0
                yield event
            if self._current_input and output_parts:
                self._pairs.append(
                    TrainingPair(
                        instruction=self._current_input,
                        output="".join(output_parts),
                        model_used=model or "unknown",
                        tokens=tokens,
                        cost=cost,
                    )
                )

        return _mw

    def export(self, format: str = "alpaca") -> TrainingDataset:
        """Export collected pairs as a TrainingDataset."""
        return TrainingDataset(
            name="agent-distillation-dataset",
            format=format,
            pairs=list(self._pairs),
            total_pairs=len(self._pairs),
            total_tokens=sum(p.tokens for p in self._pairs),
            total_cost=sum(p.cost for p in self._pairs),
        )

    @property
    def pair_count(self) -> int:
        return len(self._pairs)

    def clear(self) -> None:
        self._pairs.clear()

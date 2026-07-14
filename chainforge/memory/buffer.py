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
"""Buffer memory — keeps a sliding window of recent messages."""

from __future__ import annotations

from collections import deque

from pydantic import BaseModel, Field, model_validator

from chainforge.core.message import Message


class BufferMemory(BaseModel):
    """In-memory conversation buffer with optional window size."""

    max_messages: int = Field(default=50, description="Max messages to retain")
    messages: list[Message] = Field(default_factory=list, description="Message history")

    def add(self, msg: Message) -> None:
        self.messages.append(msg)
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages :]

    def get_history(self) -> list[Message]:
        return list(self.messages)

    def clear(self) -> None:
        self.messages.clear()

    async def load(self) -> list[Message]:
        return self.get_history()

    async def save(self, incoming: list[Message]) -> None:
        for m in incoming:
            self.add(m)

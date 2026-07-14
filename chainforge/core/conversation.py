# Copyright 2024 ChainForge Contributors
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
"""Conversation — manage, serialize, and resume agent conversations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from chainforge.core.message import Message, Role
from chainforge.logging import get_logger

logger = get_logger("core.conversation")


class Conversation:
    """Manages a conversation with message history, save/load, and resumption."""

    def __init__(
        self,
        messages: list[Message] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.messages: list[Message] = messages or []
        self.metadata: dict[str, Any] = metadata or {}
        self._last_output: str = ""

    def add_user_message(self, content: str) -> None:
        self.messages.append(Message(role=Role.user, content=content))

    def add_assistant_message(self, content: str) -> None:
        self.messages.append(Message(role=Role.assistant, content=content))

    def add_message(self, role: str | Role, content: str) -> None:
        if isinstance(role, str):
            try:
                role = Role(role)
            except ValueError:
                role = Role.user
        self.messages.append(Message(role=role, content=content))

    def to_message_list(self) -> list[Message]:
        return list(self.messages)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": "1.0",
            "metadata": dict(self.metadata),
            "messages": [
                {"role": m.role.value if hasattr(m.role, "value") else str(m.role), "content": m.content or ""}
                for m in self.messages
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Conversation:
        messages = []
        for m in data.get("messages", []):
            role_str = m.get("role", "user")
            try:
                role = Role(role_str)
            except ValueError:
                role = Role.user
            messages.append(Message(role=role, content=m.get("content", "")))
        return cls(messages=messages, metadata=data.get("metadata", {}))

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False))
        logger.info(f"Conversation saved to {path} ({len(self.messages)} messages)")

    @classmethod
    def load(cls, path: str | Path) -> Conversation:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Conversation file not found: {path}")
        return cls.from_dict(json.loads(path.read_text()))

    async def run(self, agent: Any, prompt: str | None = None) -> Any:
        if prompt:
            self.add_user_message(prompt)

        stream = await agent.run(self.to_message_list())

        # Wrap stream to capture assistant responses
        async def _capture():
            text_parts = []
            async for event in stream:
                if hasattr(event, "type") and event.type == "text" and event.content:
                    text_parts.append(event.content)
                yield event
            if text_parts:
                self.add_assistant_message("".join(text_parts))

        return _capture()

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def last_output(self) -> str:
        return self._last_output

    def summary(self) -> str:
        if not self.messages:
            return "(empty conversation)"
        turns = []
        for m in self.messages[-10:]:
            content = (m.content or "")[:100]
            role_s = m.role.value if hasattr(m.role, "value") else str(m.role)
            turns.append(f"[{role_s}] {content}")
        return "\n".join(turns)

    def clear(self) -> None:
        self.messages.clear()
        self._last_output = ""

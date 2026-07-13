"""Summary memory — compresses conversation history into a running summary."""

from __future__ import annotations

from pydantic import BaseModel, Field

from chainforge.core.message import Message


class SummaryMemory(BaseModel):
    """Conversation memory that maintains a running summary.

    Useful for long conversations where full history is too large.
    """

    summary: str = Field(default="", description="Running summary of conversation")
    recent_messages: list[Message] = Field(default_factory=list, description="Last N messages")
    max_recent: int = Field(default=10, description="Recent messages to keep verbatim")

    async def load(self) -> list[Message]:
        recent = Message.system(f"Conversation summary: {self.summary}") if self.summary else Message.system("No prior conversation.")
        return [recent] + self.recent_messages

    async def save(self, messages: list[Message]) -> None:
        # Append new messages to recent buffer
        for m in messages:
            self.recent_messages.append(m)

        # Trim recent buffer
        if len(self.recent_messages) > self.max_recent:
            self.recent_messages = self.recent_messages[-self.max_recent :]

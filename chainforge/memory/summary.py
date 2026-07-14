"""Summary memory — compresses conversation history into a running summary."""

from __future__ import annotations

from pydantic import BaseModel, Field

from chainforge.core.message import Message


SUMMARY_COMPRESS_PROMPT = """Summarize the following conversation, keeping key information, decisions, and context for future reference.

Conversation:
{content}

Provide a concise summary:"""


class SummaryMemory(BaseModel):
    """Conversation memory that maintains a running summary.

    Useful for long conversations where full history is too large.
    Call compress(llm) to generate a running summary from recent_messages.
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

        # Auto-summarize when buffer is more than 2x capacity
        if len(self.recent_messages) > self.max_recent * 2:
            old = self.recent_messages[:-self.max_recent]
            self.recent_messages = self.recent_messages[-self.max_recent:]
            old_text = "\n".join(
                f"{m.role}: {m.content}" for m in old if m.content
            )
            if old_text:
                prefix = f"[{len(old)} older messages auto-summarized]"
                self.summary = f"{self.summary}\n{prefix}" if self.summary else prefix
        elif len(self.recent_messages) > self.max_recent:
            self.recent_messages = self.recent_messages[-self.max_recent :]

    async def compress(self, llm: "LLM") -> str:
        """Generate a running summary from recent_messages using the given LLM.

        Calls llm.generate() with a summarization prompt + the recent message content,
        then sets self.summary to the result and clears recent_messages.

        Returns the generated summary string.
        """
        from chainforge.core.llm import LLM as _LLMType

        if not self.recent_messages:
            return self.summary

        content = "\n".join(
            f"[{m.role.value}] {m.content or ''}"
            for m in self.recent_messages
            if m.content
        )
        if not content:
            return self.summary

        prompt = SUMMARY_COMPRESS_PROMPT.format(content=content)
        response = await llm.generate([Message.user(prompt)])
        new_summary = response.content or ""

        if new_summary:
            # Combine with existing summary
            if self.summary:
                self.summary = f"{self.summary}\n{new_summary}"
            else:
                self.summary = new_summary
            self.recent_messages.clear()

        return self.summary

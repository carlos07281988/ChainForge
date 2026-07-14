"""ChatPromptTemplate — structured chat message templates."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from chainforge.core.message import Message, Role
from chainforge.prompts.template import PromptTemplate


class MessagePlaceholder(BaseModel):
    """A placeholder that will be replaced with a list of messages at format time.

    Usage:
        tmpl = ChatPromptTemplate.from_messages([
            ("system", "You are helpful."),
            MessagePlaceholder(variable_name="history"),
            ("user", "{input}"),
        ])
        messages = tmpl.format_messages(
            input="Hello!",
            history=[Message(role="user", content="Previous Q"), Message(role="assistant", content="Previous A")],
        )
    """

    variable_name: str = Field(description="Variable name to replace with message list")

    def format(self, messages: list[Message]) -> list[Message]:
        return messages


class ChatPromptTemplate(BaseModel):
    """Template for structured chat conversations.

    Builds a list of Message objects from role-template pairs.

    Usage:
        tmpl = ChatPromptTemplate.from_messages([
            ("system", "You are a {role} expert."),
            ("user", "Tell me about {topic}"),
        ])
        messages = tmpl.format_messages(role="Python", topic="async IO")
    """

    messages: list = Field(description="List of (role, template) pairs or MessagePlaceholders")

    model_config = {"arbitrary_types_allowed": True}

    @classmethod
    def from_messages(cls, messages: list) -> ChatPromptTemplate:
        """Create from a list of (role, template) tuples or placeholders.

        Args:
            messages: List of (role_str, template_str) tuples or MessagePlaceholder instances.

        Returns:
            ChatPromptTemplate.
        """
        validated = []
        for msg in messages:
            if isinstance(msg, tuple):
                role, template = msg
                if isinstance(template, str):
                    validated.append((role, PromptTemplate(template=template)))
                else:
                    validated.append((role, template))
            else:
                validated.append(msg)
        return cls(messages=validated)

    def format_messages(self, **kwargs: Any) -> list[Message]:
        """Format all messages with the given variables.

        Args:
            **kwargs: Variable values for all templates.

        Returns:
            List of chainforge Message objects.
        """
        result = []
        for msg in self.messages:
            if isinstance(msg, MessagePlaceholder):
                # Insert messages from variable
                var_messages = kwargs.get(msg.variable_name, [])
                if isinstance(var_messages, list):
                    result.extend(var_messages)
                continue

            role_str, template = msg
            formatted = template.format(**kwargs)

            # Map role string to Role enum
            role_enum = self._parse_role(role_str)
            result.append(Message(role=role_enum, content=formatted))

        return result

    def format_prompt(self, **kwargs: Any) -> str:
        """Format all messages into a single string (for non-chat LLMs)."""
        parts = []
        for msg in self.messages:
            if isinstance(msg, MessagePlaceholder):
                var_msgs = kwargs.get(msg.variable_name, [])
                for m in var_msgs:
                    parts.append(f"{m.role}: {m.content}")
                continue
            role_str, template = msg
            formatted = template.format(**kwargs)
            parts.append(f"{role_str.capitalize()}: {formatted}")
        return "\n".join(parts)

    @staticmethod
    def _parse_role(role: str) -> Role:
        mapping = {
            "system": Role.system,
            "user": Role.user,
            "assistant": Role.assistant,
            "ai": Role.assistant,
            "human": Role.user,
        }
        return mapping.get(role.lower(), Role.user)

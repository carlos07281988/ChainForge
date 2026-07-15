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
"""Message types — the universal conversation primitives with multi-modal support."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Role(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


class ToolCall(BaseModel):
    """A tool invocation requested by the model."""

    id: str = Field(description="Unique identifier for this tool call")
    name: str = Field(description="Tool name")
    args: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")


class ToolResult(BaseModel):
    """The result of executing a tool call."""

    tool_call_id: str = Field(description="Matching ToolCall.id")
    name: str = Field(description="Tool name")
    content: str = Field(default="", description="Tool output content")
    is_error: bool = Field(default=False, description="Whether the tool raised")


class ContentPartType(str, Enum):
    """Types of content parts for multi-modal messages."""
    text = "text"
    image_url = "image_url"
    file = "file"
    audio = "audio"


class ContentPart(BaseModel):
    """A single part of a multi-modal message content.

    Supports text, image URLs, file references, and audio.
    """

    type: ContentPartType = Field(default=ContentPartType.text)
    text_data: str | None = Field(default=None, description="Text content")
    image_url: str | None = Field(default=None, description="Image URL or base64 data URI")
    file_path: str | None = Field(default=None, description="Local file path")
    file_data: str | None = Field(default=None, description="Base64-encoded file data")
    mime_type: str | None = Field(default=None, description="MIME type (image/png, audio/wav, etc.)")
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_text(cls, content: str) -> "ContentPart":
        return cls(type=ContentPartType.text, text_data=content)

    @classmethod
    def from_image_url(cls, url: str, detail: str = "auto") -> "ContentPart":
        return cls(type=ContentPartType.image_url, image_url=url, metadata={"detail": detail})

    @classmethod
    def from_image_file(cls, file_path: str, mime_type: str = "image/png") -> "ContentPart":
        return cls(type=ContentPartType.image_url, file_path=file_path, mime_type=mime_type)

    @classmethod
    def from_audio_file(cls, file_path: str, mime_type: str = "audio/wav") -> "ContentPart":
        return cls(type=ContentPartType.audio, file_path=file_path, mime_type=mime_type)

    def to_openai_part(self) -> dict[str, Any]:
        """Convert to an OpenAI-compatible content part dict."""
        if self.type == ContentPartType.text:
            return {"type": "text", "text": self.text_data or ""}
        if self.type == ContentPartType.image_url:
            url = self.image_url or ""
            if self.file_path and not url:
                import base64
                with open(self.file_path, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode()
                    url = f"data:{self.mime_type or 'image/png'};base64,{encoded}"
            return {"type": "image_url", "image_url": {"url": url, "detail": self.metadata.get("detail", "auto")}}
        return {"type": "text", "text": str(self)}


class Message(BaseModel):
    """A single message in a conversation, with multi-modal support.

    Supports both simple text content and multi-modal content parts
    (images, files, audio) via the `parts` field.
    """

    role: Role = Field(description="Message role")
    content: str | None = Field(default=None, description="Text content")
    parts: list[ContentPart] | None = Field(default=None, description="Multi-modal content parts")
    tool_calls: list[ToolCall] | None = Field(default=None, description="Tool calls from assistant")
    tool_call_id: str | None = Field(default=None, description="Tool result reference")
    name: str | None = Field(default=None, description="Tool name for tool results")
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def system(cls, content: str, **kwargs) -> "Message":
        return cls(role=Role.system, content=content, **kwargs)

    @classmethod
    def user(cls, content: str, **kwargs) -> "Message":
        return cls(role=Role.user, content=content, **kwargs)

    @classmethod
    def user_with_images(cls, text: str, image_urls: list[str], **kwargs) -> "Message":
        """Create a user message with text and images."""
        parts = [ContentPart.from_text(text)]
        parts.extend(ContentPart.from_image_url(url) for url in image_urls)
        return cls(role=Role.user, content=text, parts=parts, **kwargs)

    @classmethod
    def user_with_files(cls, text: str, file_paths: list[str], **kwargs) -> "Message":
        """Create a user message with text and file attachments."""
        parts = [ContentPart.from_text(text)]
        import mimetypes
        for fp in file_paths:
            mime, _ = mimetypes.guess_type(fp)
            if mime and mime.startswith("image/"):
                parts.append(ContentPart.from_image_file(fp, mime or "image/png"))
            else:
                parts.append(ContentPart(type=ContentPartType.file, file_path=fp, mime_type=mime or "application/octet-stream"))
        return cls(role=Role.user, content=text, parts=parts, **kwargs)

    @classmethod
    def assistant(cls, content: str | None = None, tool_calls: list[ToolCall] | None = None, **kwargs) -> "Message":
        return cls(role=Role.assistant, content=content, tool_calls=tool_calls, **kwargs)

    @classmethod
    def tool_result(cls, tool_call_id: str, name: str, content: str, is_error: bool = False) -> "Message":
        return cls(
            role=Role.tool,
            content=content,
            tool_call_id=tool_call_id,
            name=name,
            metadata={"is_error": is_error},
        )

    def model_dump_openai(self) -> dict:
        """Dump to OpenAI-compatible dict, with multi-modal support."""
        base: dict[str, Any] = {"role": self.role.value}

        # Multi-modal content: use parts if available
        if self.parts:
            base["content"] = [p.to_openai_part() for p in self.parts]
        elif self.content is not None:
            base["content"] = self.content

        if self.tool_calls:
            base["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.args},
                }
                for tc in self.tool_calls
            ]
        if self.tool_call_id:
            base["tool_call_id"] = self.tool_call_id
        if self.name:
            base["name"] = self.name
        return base

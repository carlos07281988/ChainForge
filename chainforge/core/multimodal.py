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
"""Multi-Modal Pipeline — load and process images, audio, and files for LLM input.

Provides unified utilities for loading media files and wrapping them
as Message ContentParts suitable for vision-capable LLM providers.

Usage:
    from chainforge.core.multimodal import image_to_message, file_to_message

    # Load an image and create a user message with it
    msg = image_to_message("chart.png", "Analyze this chart")
    stream = await agent.run(msg)

    # The provider automatically handles image parts
"""

from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path
from typing import Any

from chainforge.core.message import ContentPart, ContentPartType, Message


def load_image_data(path: str) -> tuple[str, str]:
    """Load an image file and return (base64_data, mime_type).

    Args:
        path: Path to image file (png, jpg, gif, webp).

    Returns:
        Tuple of (base64_encoded_data, mime_type_string).
    """
    path = str(path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Image not found: {path}")

    mime_type, _ = mimetypes.guess_type(path)
    if mime_type is None:
        ext = Path(path).suffix.lower()
        mime_map = {
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
        }
        mime_type = mime_map.get(ext, "image/png")

    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    return encoded, mime_type


def image_to_message(
    image_path: str,
    text: str = "",
    detail: str = "auto",
) -> Message:
    """Create a user Message with an image attachment.

    Args:
        image_path: Path to image file.
        text: Optional text prompt accompanying the image.
        detail: Image detail level ('auto', 'low', 'high').

    Returns:
        A Message with role=user containing the image as a ContentPart.
    """
    encoded, mime_type = load_image_data(image_path)
    data_uri = f"data:{mime_type};base64,{encoded}"

    parts = []
    if text:
        parts.append(ContentPart.from_text(text))
    parts.append(
        ContentPart(
            type=ContentPartType.image_url,
            image_url=data_uri,
            mime_type=mime_type,
            metadata={"detail": detail},
        )
    )

    return Message(role="user", content=text or "", parts=parts)


def file_to_message(
    file_path: str,
    text: str = "",
) -> Message:
    """Create a user Message with a file attachment.

    Automatically detects file type and creates appropriate ContentParts.
    For images, this is equivalent to image_to_message.
    For other files, creates a text description with file metadata.

    Args:
        file_path: Path to the file.
        text: Optional text prompt.

    Returns:
        A Message with role=user containing the file content.
    """
    path = str(file_path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")

    mime_type, _ = mimetypes.guess_type(path)
    mime_type = mime_type or "application/octet-stream"
    filename = Path(path).name

    # If it's an image, use image_to_message
    if mime_type and mime_type.startswith("image/"):
        return image_to_message(path, text)

    # For other files, load as text and create a text-based message
    try:
        with open(path, "r", encoding="utf-8") as f:
            file_content = f.read()
    except (UnicodeDecodeError, Exception):
        file_content = f"[Binary file: {filename}, {os.path.getsize(path)} bytes, {mime_type}]"

    content_parts = [text, f"\n--- File: {filename} ---\n{file_content[:5000]}"]
    return Message.user("\n".join(filter(None, content_parts)))


__all__ = ["load_image_data", "image_to_message", "file_to_message"]

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
"""VisionTool -- image encoding and multi-modal content preparation."""

from __future__ import annotations

import base64
import hashlib
import mimetypes
import time
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from pydantic import BaseModel, ConfigDict, Field

from chainforge.core.message import ContentPart

# Supported image MIME types in preferred order
_SUPPORTED_TYPES: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def _detect_mime_type(path: str) -> str:
    """Detect MIME type from file extension, with fallback."""
    ext = Path(path).suffix.lower()
    if ext in _SUPPORTED_TYPES:
        return _SUPPORTED_TYPES[ext]
    guessed, _ = mimetypes.guess_type(path)
    if guessed and guessed.startswith("image/"):
        return guessed
    return "image/png"


class ImageContent(BaseModel):
    """Encoded image content ready for multi-modal model consumption."""

    image_path: str = Field(description="Original file path or URL")
    encoding: str = Field(default="base64", description="Encoding format")
    mime_type: str = Field(default="image/png", description="MIME type of the image")
    base64_data: str = Field(default="", description="Base64-encoded image bytes")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Extra metadata (dimensions, size, etc.)")

    def to_data_uri(self) -> str:
        """Return the image as a `data:` URI string."""
        return f"data:{self.mime_type};{self.encoding},{self.base64_data}"

    def to_content_part(self, detail: str = "auto") -> ContentPart:
        """Convert to a ``ContentPart`` suitable for the core Message pipeline."""
        return ContentPart.from_image_url(self.to_data_uri(), detail=detail)


class VisionTool(BaseModel):
    """Tool that converts images to base64 and wraps them as ``ContentPart`` objects.

    Supports local files (PNG, JPEG, WebP, GIF) and URL-based images.
    MIME type is auto-detected from the file extension.

    Usage::

        tool = VisionTool()
        content = tool.process("screenshot.png")
        # content.base64_data, content.mime_type, etc.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    max_file_size_mb: float = Field(default=20.0, description="Max image size in MB before rejection")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, image_path: str) -> ImageContent:
        """Read an image, encode as base64, and return an ``ImageContent``.

        Hosts ``image_path`` either a local path or an HTTP/HTTPS URL.
        """
        raw_bytes = self._read_bytes(image_path)
        return self._encode(image_path, raw_bytes)

    def process_to_part(self, image_path: str, detail: str = "auto") -> ContentPart:
        """Shortcut: process an image and return a ``ContentPart`` directly."""
        content = self.process(image_path)
        return content.to_content_part(detail=detail)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_bytes(self, image_path: str) -> bytes:
        """Read raw bytes from a local file or URL."""
        if image_path.startswith(("http://", "https://")):
            return self._download(image_path)
        return self._read_local(image_path)

    def _read_local(self, image_path: str) -> bytes:
        path = Path(image_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")
        file_size_mb = path.stat().st_size / (1024 * 1024)
        if file_size_mb > self.max_file_size_mb:
            raise ValueError(
                f"Image size {file_size_mb:.1f} MB exceeds limit of {self.max_file_size_mb} MB"
            )
        return path.read_bytes()

    def _download(self, url: str) -> bytes:
        """Download an image from a URL (synchronous, for tool use)."""
        with urlopen(url, timeout=30) as resp:
            data = resp.read()
        file_size_mb = len(data) / (1024 * 1024)
        if file_size_mb > self.max_file_size_mb:
            raise ValueError(
                f"Downloaded image size {file_size_mb:.1f} MB exceeds limit of {self.max_file_size_mb} MB"
            )
        return data

    def _encode(self, image_path: str, raw_bytes: bytes) -> ImageContent:
        """Encode raw bytes as base64 and populate metadata."""
        mime_type = _detect_mime_type(image_path)
        b64 = base64.b64encode(raw_bytes).decode("ascii")
        return ImageContent(
            image_path=image_path,
            encoding="base64",
            mime_type=mime_type,
            base64_data=b64,
            metadata={
                "size_bytes": len(raw_bytes),
                "sha256": hashlib.sha256(raw_bytes).hexdigest(),
                "timestamp": time.time(),
            },
        )

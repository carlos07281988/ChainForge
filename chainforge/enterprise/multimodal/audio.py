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
"""AudioTool -- transcription and audio content preparation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from chainforge.core.message import ContentPart, ContentPartType


class AudioContent(BaseModel):
    """Audio content with transcription metadata."""

    audio_path: str = Field(description="Original audio file path")
    transcription: str = Field(default="", description="Transcribed text from the audio")
    duration_seconds: float = Field(default=0.0, description="Audio duration in seconds")
    language: str = Field(default="en", description="Detected or specified language code")
    segments: list[dict[str, Any]] = Field(default_factory=list, description="Time-stamped transcription segments")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Extra metadata")

    def to_text(self) -> str:
        """Return the plain transcription text."""
        return self.transcription

    def to_content_part(self) -> ContentPart:
        """Convert to a ``ContentPart`` for the core Message pipeline."""
        return ContentPart(
            type=ContentPartType.audio,
            file_path=self.audio_path,
            mime_type="audio/wav",
            text_data=self.transcription,
            metadata={
                **self.metadata,
                "duration_seconds": self.duration_seconds,
                "language": self.language,
            },
        )


class AudioTool(BaseModel):
    """Tool that transcribes audio files into text.

    In production mode this delegates to Whisper, AssemblyAI, or Deepgram.
    In stub mode (the default) it returns a placeholder transcription so that
    the multi-modal pipeline can be tested without API keys.

    Usage::

        tool = AudioTool(mode="stub")
        content = tool.process("call_recording.wav")
        print(content.transcription)
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    mode: str = Field(default="stub", description="Transcription mode: 'stub', 'whisper', 'assemblyai', or 'deepgram'")
    api_key: str | None = Field(default=None, description="API key for cloud transcription services")
    language_hint: str = Field(default="en", description="Language hint for transcription")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, audio_path: str) -> AudioContent:
        """Transcribe an audio file and return ``AudioContent``."""
        if self.mode == "stub":
            return self._stub_transcribe(audio_path)
        if self.mode == "whisper":
            return self._whisper_transcribe(audio_path)
        if self.mode == "assemblyai":
            return self._assemblyai_transcribe(audio_path)
        if self.mode == "deepgram":
            return self._deepgram_transcribe(audio_path)
        raise ValueError(f"Unknown transcription mode: {self.mode}")

    def process_to_part(self, audio_path: str) -> ContentPart:
        """Shortcut: transcribe audio and return a ``ContentPart`` directly."""
        content = self.process(audio_path)
        return content.to_content_part()

    # ------------------------------------------------------------------
    # Stub transcription (no API key needed)
    # ------------------------------------------------------------------

    def _stub_transcribe(self, audio_path: str) -> AudioContent:
        """Return a placeholder transcription for testing.

        In a real deployment, replace with an actual API call.
        """
        path = Path(audio_path)
        file_size = path.stat().st_size if path.exists() else 0
        return AudioContent(
            audio_path=str(audio_path),
            transcription=f"[STUB] Transcription of {path.name} — "
            f"this is a placeholder. Configure mode='whisper' / 'assemblyai' / 'deepgram' "
            f"and provide an api_key for real transcription.",
            duration_seconds=60.0,
            language=self.language_hint,
            segments=[
                {"start": 0.0, "end": 60.0, "text": "[STUB] placeholder segment"}
            ],
            metadata={
                "mode": "stub",
                "file_size_bytes": file_size,
            },
        )

    # ------------------------------------------------------------------
    # Real transcription backends (stubs — implement in production)
    # ------------------------------------------------------------------

    def _whisper_transcribe(self, audio_path: str) -> AudioContent:
        """Transcribe using OpenAI Whisper API.

        Production implementation: POST to https://api.openai.com/v1/audio/transcriptions.
        """
        # TODO: implement in production with
        #   import openai
        #   audio_file = open(audio_path, "rb")
        #   transcript = openai.Audio.transcribe("whisper-1", audio_file)
        raise NotImplementedError(
            "Whisper transcription is not yet implemented. "
            "Use mode='stub' for testing, or wire up the OpenAI API."
        )

    def _assemblyai_transcribe(self, audio_path: str) -> AudioContent:
        """Transcribe using AssemblyAI.

        Production implementation: upload file, poll transcript endpoint.
        """
        raise NotImplementedError(
            "AssemblyAI transcription is not yet implemented. "
            "Use mode='stub' for testing, or wire up the AssemblyAI API."
        )

    def _deepgram_transcribe(self, audio_path: str) -> AudioContent:
        """Transcribe using Deepgram.

        Production implementation: POST to Deepgram's speech-to-text endpoint.
        """
        raise NotImplementedError(
            "Deepgram transcription is not yet implemented. "
            "Use mode='stub' for testing, or wire up the Deepgram API."
        )

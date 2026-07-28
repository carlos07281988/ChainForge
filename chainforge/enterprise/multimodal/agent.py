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
"""MultiModalAgent -- wraps ChainForge Agent with automatic multi-modal input handling."""

from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from chainforge.core.agent import Agent
from chainforge.core.llm import LLM
from chainforge.core.message import ContentPart, Message, Role
from chainforge.core.tool import Tool
from chainforge.enterprise.multimodal.audio import AudioContent, AudioTool
from chainforge.enterprise.multimodal.memory import InteractionRecord, MultiModalMemory
from chainforge.enterprise.multimodal.vision import ImageContent, VisionTool

# ---------------------------------------------------------------------------
# Type aliases for clarity
# ---------------------------------------------------------------------------
MultiModalInput = str | ImageContent | AudioContent


class MultiModalAgent(BaseModel):
    """Agent that automatically handles mixed text, image, and audio inputs.

    Accepts a heterogeneous list of ``MultiModalInput`` items and runs a
    pre-processing pipeline before delegating to the core ``Agent``:

    1. **Text inputs** pass through unchanged.
    2. **Image inputs** are encoded as base64 ``ContentPart`` objects.
    3. **Audio inputs** are transcribed via ``AudioTool`` and appended as text.
    4. All content is combined into a single ``Message`` list and sent to the agent.

    After execution, the interaction is persisted in ``MultiModalMemory``.

    Usage::

        agent = MultiModalAgent(
            agent=Agent(llm=OpenAIProvider()),
            vision=VisionTool(),
            audio=AudioTool(mode="stub"),
        )
        response = await agent.run([
            "What is in this image?",
            ImageContent(image_path="photo.jpg", ...),
        ])
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent: Agent = Field(description="Wrapped ChainForge Agent instance")
    vision: VisionTool = Field(default_factory=VisionTool, description="Image encoding pipeline")
    audio: AudioTool = Field(default_factory=AudioTool, description="Audio transcription pipeline")
    memory: MultiModalMemory = Field(default_factory=MultiModalMemory, description="Interaction memory store")
    system_prompt: str | None = Field(default=None, description="Override system prompt")

    # ------------------------------------------------------------------
    # Pre-processing pipeline
    # ------------------------------------------------------------------

    def preprocess(self, inputs: list[MultiModalInput]) -> tuple[str, list[ContentPart]]:
        """Process mixed inputs into a combined text prompt and ContentPart list.

        Returns
        -------
        ``(combined_text, content_parts)`` where:
        - *combined_text* is the concatenation of all text inputs plus
          transcribed audio.
        - *content_parts* contains base64-encoded images ready for the model.
        """
        text_parts: list[str] = []
        content_parts: list[ContentPart] = []

        for item in inputs:
            if isinstance(item, str):
                text_parts.append(item)

            elif isinstance(item, ImageContent):
                # If already base64, use as-is; otherwise read & encode
                if item.base64_data:
                    content_parts.append(item.to_content_part())
                else:
                    encoded = self.vision.process(item.image_path)
                    content_parts.append(encoded.to_content_part())

            elif isinstance(item, AudioContent):
                # Transcribe audio and prepend a label
                transcribed = self.audio.process(item.audio_path)
                text_parts.append(
                    f"[Audio Transcription: {item.audio_path}]\n{transcribed.transcription}"
                )

        combined_text = "\n\n".join(text_parts)
        return combined_text, content_parts

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run(
        self,
        inputs: list[MultiModalInput],
        user_prompt: str | None = None,
        **run_kwargs: Any,
    ) -> str:
        """Run the agent with multi-modal inputs and return the final response text.

        Parameters
        ----------
        inputs:
            Mixed list of ``str``, ``ImageContent``, and ``AudioContent``.
        user_prompt:
            Convenience override — if given, prepends to the combined text.
        run_kwargs:
            Passed through to ``agent.run()``.
        """
        combined_text, content_parts = self.preprocess(inputs)

        if user_prompt:
            combined_text = user_prompt + "\n\n" + combined_text

        # Build the message for the agent
        message = Message(
            role=Role.user,
            content=combined_text,
            parts=content_parts if content_parts else None,
        )

        # Collect response
        response_parts: list[str] = []
        async for event in self.agent.run(message.content, **run_kwargs):
            response_parts.append(str(event))

        final_response = "\n".join(response_parts)

        # Persist in memory
        self._record(inputs, combined_text, final_response)

        return final_response

    async def run_sync(
        self,
        inputs: list[MultiModalInput],
        user_prompt: str | None = None,
        **run_kwargs: Any,
    ) -> str:
        """Synchronous convenience wrapper around ``run()``."""
        return await self.run(inputs, user_prompt=user_prompt, **run_kwargs)

    # ------------------------------------------------------------------
    # Memory helpers
    # ------------------------------------------------------------------

    def _record(
        self,
        inputs: list[MultiModalInput],
        combined_text: str,
        response_text: str,
    ) -> None:
        """Create and store an ``InteractionRecord`` in memory."""
        record = InteractionRecord(
            id=uuid.uuid4().hex,
            timestamp=time.time(),
            text_content=combined_text,
            image_paths=[
                item.image_path for item in inputs if isinstance(item, ImageContent)
            ],
            audio_paths=[
                item.audio_path for item in inputs if isinstance(item, AudioContent)
            ],
            model_used=self.agent.llm.model if hasattr(self.agent.llm, "model") else None,
            response_text=response_text,
        )
        self.memory.add(record)

    # ------------------------------------------------------------------
    # Convenience: default agent factory
    # ------------------------------------------------------------------

    @classmethod
    def from_llm(
        cls,
        llm: LLM,
        tools: list[Tool] | None = None,
        vision: VisionTool | None = None,
        audio: AudioTool | None = None,
        memory: MultiModalMemory | None = None,
        system_prompt: str | None = None,
    ) -> "MultiModalAgent":
        """Create a ``MultiModalAgent`` from a bare ``LLM`` instance.

        A convenience factory that builds an ``Agent`` internally.

        Usage::

            mma = MultiModalAgent.from_llm(
                OpenAIProvider(model="gpt-4o"),
                system_prompt="You are a helpful assistant.",
            )
        """
        agent = Agent(
            llm=llm,
            tools=tools or [],
            system_prompt=system_prompt,
        )
        return cls(
            agent=agent,
            vision=vision or VisionTool(),
            audio=audio or AudioTool(),
            memory=memory or MultiModalMemory(),
            system_prompt=system_prompt,
        )

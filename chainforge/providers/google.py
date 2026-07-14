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
"""Google Gemini provider — wraps the Google Generative AI API."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from chainforge.core.errors import ProviderError
from chainforge.core.llm import LLM, LLMResponse
from chainforge.core.message import Message, Role
from chainforge.core.tool import ToolSpec


class GoogleProvider(BaseModel):
    """Google Gemini LLM provider.

    Usage:
        llm = GoogleProvider(model="gemini-2.0-flash")
        response = await llm.generate(messages)

    WARNING: genai.configure() sets global SDK state in the google-generativeai
    library, so only one GoogleProvider instance with one API key can be active
    per process. Creating a second GoogleProvider with a different API key will
    overwrite the first instance's configuration, causing the first instance to
    use the second instance's API key.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model: str = Field(default="gemini-2.0-flash")
    api_key: str | None = Field(default=None)

    def _get_client(self):
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError(
                "Google provider requires `google-generativeai` package. "
                "Install with: pip install 'chainforge[google]'"
            )
        api_key = self.api_key or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ProviderError("GOOGLE_API_KEY not set")
        genai.configure(api_key=api_key)
        return genai

    def _to_google_messages(self, messages: list[Message]) -> tuple[list[dict], str | None]:
        """Convert ChainForge messages to Gemini format."""
        system_prompt = None
        history = []
        for m in messages:
            if m.role == Role.system:
                system_prompt = m.content
                continue
            parts = []
            if m.content:
                parts.append({"text": m.content})
            if m.tool_calls:
                for tc in m.tool_calls:
                    parts.append({
                        "functionCall": {"name": tc.name, "args": tc.args},
                    })
            if m.role == Role.tool:
                parts.append({
                    "functionResponse": {
                        "name": m.name or "",
                        "response": {"content": m.content or ""},
                    },
                })
            role = "model" if m.role == Role.assistant else "user"
            history.append({"role": role, "parts": parts})
        return history, system_prompt

    def _to_google_tools(self, tools: list[ToolSpec] | None) -> list[dict] | None:
        if not tools:
            return None
        google_tools = []
        for t in tools:
            google_tools.append({
                "function_declarations": [{
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                }],
            })
        return google_tools

    def _parse_response(self, candidate: Any) -> LLMResponse:
        content_parts = []
        tool_calls = []
        for part in candidate.content.parts:
            if hasattr(part, "text") and part.text:
                content_parts.append(part.text)
            if hasattr(part, "function_call") and part.function_call:
                fc = part.function_call
                tool_calls.append({
                    "id": fc.name,
                    "type": "function",
                    "function": {
                        "name": fc.name,
                        "arguments": {k: v for k, v in fc.args.items()},
                    },
                })
        usage = None
        if hasattr(candidate, "usage_metadata") and candidate.usage_metadata:
            usage = {
                "prompt_tokens": candidate.usage_metadata.prompt_token_count or 0,
                "completion_tokens": candidate.usage_metadata.candidates_token_count or 0,
                "total_tokens": candidate.usage_metadata.total_token_count or 0,
            }
        return LLMResponse(
            content="".join(content_parts) if content_parts else None,
            tool_calls=tool_calls or None,
            usage=usage,
            model=self.model,
            finish_reason=str(candidate.finish_reason) if candidate.finish_reason else None,
        )

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        genai = self._get_client()
        history, system_prompt = self._to_google_messages(messages)
        google_tools = self._to_google_tools(tools)

        try:
            model = genai.GenerativeModel(
                model_name=self.model,
                system_instruction=system_prompt,
                tools=google_tools,
            )
            # Last message is the current turn
            if history:
                last = history.pop()
            else:
                last = {"role": "user", "parts": [{"text": messages[-1].content if messages else "Hello"}]}

            chat = model.start_chat(history=history)
            raw = await chat.send_message_async(last["parts"], **kwargs)
            candidate = raw.candidates[0] if raw.candidates else raw._result.candidates[0]
            return self._parse_response(candidate)
        except Exception as e:
            raise ProviderError(f"Google API error: {e}") from e

    async def stream_generate(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str | LLMResponse]:
        genai = self._get_client()
        history, system_prompt = self._to_google_messages(messages)
        google_tools = self._to_google_tools(tools)

        try:
            model = genai.GenerativeModel(
                model_name=self.model,
                system_instruction=system_prompt,
                tools=google_tools,
            )
            if history:
                last = history.pop()
            else:
                last = {"role": "user", "parts": [{"text": messages[-1].content if messages else "Hello"}]}

            chat = model.start_chat(history=history)
            response = await chat.send_message_async(last["parts"], stream=True, **kwargs)

            content_parts = []
            async for chunk in response:
                if hasattr(chunk, "text") and chunk.text:
                    yield chunk.text
                    content_parts.append(chunk.text)

            if response.candidates:
                candidate = response.candidates[0]
                yield self._parse_response(candidate)
        except Exception as e:
            raise ProviderError(f"Google API error: {e}") from e

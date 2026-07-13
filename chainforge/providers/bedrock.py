"""AWS Bedrock provider — invoke foundation models via Amazon Bedrock.

Supports Claude (Anthropic), Llama (Meta), Mistral, and Amazon Titan models.
Default model is Claude Sonnet 4 via Bedrock.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from chainforge.core.errors import ProviderError
from chainforge.core.llm import LLM, LLMResponse
from chainforge.core.message import Message, Role
from chainforge.core.tool import ToolSpec


class BedrockProvider(BaseModel):
    """AWS Bedrock LLM provider.

    Usage:
        llm = BedrockProvider(model="anthropic.claude-sonnet-4-20250514-v1:0")
        response = await llm.generate(messages)

    Requires AWS credentials configured via environment variables
    (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION) or
    boto3 credential chain.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model: str = Field(default="anthropic.claude-sonnet-4-20250514-v1:0")
    region: str | None = Field(default=None)
    max_tokens: int = Field(default=4096)

    def _get_client(self):
        try:
            import boto3
        except ImportError:
            raise ImportError(
                "Bedrock provider requires `boto3`. Install with: pip install 'chainforge[bedrock]'"
            )
        return boto3.client(
            "bedrock-runtime",
            region_name=self.region or os.environ.get("AWS_REGION", "us-east-1"),
        )

    def _to_bedrock_body(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> bytes:
        """Convert messages to Bedrock Converse API format."""
        system_msgs = [m.content for m in messages if m.role == Role.system]
        conv_messages = []
        for m in messages:
            if m.role == Role.system:
                continue
            content_list = []
            if m.content:
                content_list.append({"text": m.content})
            if m.tool_calls:
                for tc in m.tool_calls:
                    content_list.append({
                        "toolUse": {
                            "toolUseId": tc.id,
                            "name": tc.name,
                            "input": tc.args,
                        },
                    })
            if m.role == Role.tool:
                content_list.append({
                    "toolResult": {
                        "toolUseId": m.tool_call_id or "",
                        "content": [{"text": m.content or ""}],
                        "status": "error" if m.metadata.get("is_error") else "success",
                    },
                })
            role_map = {"user": "user", "assistant": "assistant", "tool": "user"}
            role = role_map.get(m.role.value, "user")
            conv_messages.append({"role": role, "content": content_list})

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self.max_tokens,
            "messages": conv_messages,
        }
        if system_msgs:
            body["system"] = [{"text": s} for s in system_msgs if s]

        if tools:
            body["toolConfig"] = {
                "tools": [
                    {
                        "toolSpec": {
                            "name": t.name,
                            "description": t.description,
                            "inputSchema": {"json": t.parameters},
                        }
                    }
                    for t in tools
                ]
            }

        return json.dumps(body).encode()

    def _parse_response(self, raw: dict) -> LLMResponse:
        content_parts = []
        tool_calls = []

        for block in raw.get("content", []):
            if block.get("type") == "text":
                content_parts.append(block.get("text", ""))
            elif block.get("type") == "toolUse":
                tc = block.get("toolUse", {})
                tool_calls.append({
                    "id": tc.get("toolUseId", ""),
                    "type": "function",
                    "function": {
                        "name": tc.get("name", ""),
                        "arguments": tc.get("input", {}),
                    },
                })

        usage = raw.get("usage", {})
        return LLMResponse(
            content="".join(content_parts) if content_parts else None,
            tool_calls=tool_calls or None,
            usage={
                "input_tokens": usage.get("inputTokens", 0),
                "output_tokens": usage.get("outputTokens", 0),
            } if usage else None,
            model=raw.get("model", self.model),
            finish_reason=raw.get("stopReason"),
        )

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        client = self._get_client()
        body = self._to_bedrock_body(messages, tools)

        try:
            import asyncio
            raw = await asyncio.to_thread(
                client.invoke_model,
                modelId=self.model,
                contentType="application/json",
                accept="application/json",
                body=body,
            )
            response_body = json.loads(raw["body"].read())
        except Exception as e:
            raise ProviderError(f"Bedrock API error: {e}") from e

        return self._parse_response(response_body)

    async def stream_generate(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str | LLMResponse]:
        client = self._get_client()
        body = self._to_bedrock_body(messages, tools)

        try:
            import asyncio
            response = await asyncio.to_thread(
                client.invoke_model_with_response_stream,
                modelId=self.model,
                contentType="application/json",
                accept="application/json",
                body=body,
            )
        except Exception as e:
            raise ProviderError(f"Bedrock API error: {e}") from e

        content_parts = []
        tool_call_deltas: dict = {}

        for event in response.get("body", []):
            chunk = json.loads(event.get("chunk", {}).get("bytes", b"{}"))
            chunk_type = chunk.get("type", "")

            if chunk_type == "content_block_delta":
                delta = chunk.get("delta", {})
                if delta.get("type") == "text_delta":
                    text = delta.get("text", "")
                    if text:
                        yield text
                        content_parts.append(text)
                elif delta.get("type") == "tool_use_delta":
                    tc_input = delta.get("input", "")
                    # Accumulate tool call input

            elif chunk_type == "content_block_start":
                start = chunk.get("content_block", {})
                if start.get("type") == "tool_use":
                    idx = chunk.get("index", len(tool_call_deltas))
                    tool_call_deltas[idx] = {
                        "id": start.get("id", "").get("toolUseId", ""),
                        "name": start.get("name", ""),
                        "input": "",
                    }

            elif chunk_type == "message_stop":
                tc_list = None
                if tool_call_deltas:
                    tc_list = []
                    for idx in sorted(tool_call_deltas):
                        d = tool_call_deltas[idx]
                        tc_list.append({
                            "id": d["id"],
                            "type": "function",
                            "function": {"name": d["name"], "arguments": d.get("input", {})},
                        })
                yield LLMResponse(
                    content="".join(content_parts) if content_parts else None,
                    tool_calls=tc_list,
                    model=self.model,
                )

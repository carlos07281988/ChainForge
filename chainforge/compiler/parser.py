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
"""NL Parser — natural language → IntentSchema.

Two modes:
  1. Template mode: match against known patterns (no LLM needed)
  2. LLM mode: use an LLM to parse arbitrary natural language

Usage:
    # Template mode (fast, deterministic)
    schema = parse_nl("search web and answer")

    # LLM mode (flexible, handles any input)
    llm = OpenAIProvider(model="gpt-4o")
    schema = await parse_nl_llm("search the web for AI news, then summarize", llm)
"""

from __future__ import annotations

import json
from typing import Any

from chainforge.compiler.schema import IntentSchema
from chainforge.compiler.templates import best_template
from chainforge.logging import get_logger

logger = get_logger("compiler.parser")

# ── System prompt for LLM mode ────────────────────────────────────────────

NL_TO_INTENT_SYSTEM_PROMPT = """You are an agent workflow compiler. Your job is to convert natural language descriptions of agent behavior into a structured JSON schema.

The schema represents a directed graph of nodes with edges. Each node is one of:
- entry: Starting point (exactly one required)
- exit: Ending point (at least one required)
- llm: An LLM call with a prompt
- tool: A tool execution (specify tool name)
- conditional: A decision point with named conditions on outgoing edges
- agent: Delegate to a sub-agent
- step: A generic processing step
- merge: Merge multiple incoming branches

Response format (JSON only, no markdown):
{
  "name": "short_name",
  "description": "what this workflow does",
  "nodes": [
    {"id": "entry", "type": "entry", "description": "Start"},
    {"id": "llm_step", "type": "llm", "description": "what to do",
     "prompt": "instruction for the LLM", "config": {}},
    {"id": "tool_step", "type": "tool", "description": "what tool does",
     "tool": "tool_name", "config": {"param": "value"}},
    {"id": "decision", "type": "conditional", "description": "check condition"},
    {"id": "exit", "type": "exit", "description": "End"}
  ],
  "edges": [
    {"source": "entry", "target": "llm_step"},
    {"source": "decision", "target": "branch_a", "condition": "condition_name"},
    {"source": "llm_step", "target": "exit"}
  ],
  "tools": ["tool_name_1", "tool_name_2"],
  "config": {}
}

Rules:
1. Every node ID must be unique
2. Every node referenced in edges must exist in nodes
3. At least one entry and one exit node
4. Conditional nodes need conditions on edges
5. Tool nodes must have a "tool" field
6. LLM nodes should have a "prompt" field
7. Keep descriptions concise but informative

Only output valid JSON. No explanation, no markdown formatting."""


# ── Template mode parser ──────────────────────────────────────────────────


def parse_nl(text: str) -> IntentSchema | None:
    """Parse natural language using template matching.

    Fast and deterministic — no LLM needed. Returns None if no template matches.

    Args:
        text: Natural language description of the workflow.

    Returns:
        IntentSchema if a template matched, None otherwise.
    """
    template = best_template(text)
    if template is None:
        return None
    logger.info(f"Template match: {template.name}")
    return template.build(text)


# ── LLM mode parser ──────────────────────────────────────────────────────


_PARSER_LLM_CACHE: dict[str, IntentSchema] = {}


async def parse_nl_llm(text: str, llm: Any,
                        max_retries: int = 2) -> IntentSchema | None:
    """Parse natural language using an LLM.

    More flexible than template mode — handles arbitrary input.

    Args:
        text: Natural language description of the workflow.
        llm: An LLM provider instance (any LLM with a `.generate()` method).
        max_retries: Max retries on JSON parse failure.

    Returns:
        IntentSchema, or None if parsing failed.
    """
    from chainforge.core.message import Message

    cache_key = text.strip().lower()
    if cache_key in _PARSER_LLM_CACHE:
        logger.info("LLM parser cache hit")
        return _PARSER_LLM_CACHE[cache_key]

    for attempt in range(max_retries + 1):
        try:
            response = await llm.generate(
                [
                    Message.system(NL_TO_INTENT_SYSTEM_PROMPT),
                    Message.user(f"Compile this agent workflow: {text}"),
                ],
                temperature=0.1,
                max_tokens=2000,
            )
            content = response.content or ""
            schema_data = _extract_json(content)
            if schema_data is None:
                logger.warning(f"LLM parse attempt {attempt + 1}: no JSON found")
                continue

            schema = IntentSchema.from_dict(schema_data)
            _PARSER_LLM_CACHE[cache_key] = schema
            logger.info(f"LLM parse succeeded: {schema.name}")
            return schema

        except Exception as e:
            logger.warning(f"LLM parse attempt {attempt + 1} failed: {e}")
            continue

    logger.error(f"LLM parse failed after {max_retries + 1} attempts")
    return None


def _extract_json(text: str) -> dict[str, Any] | None:
    """Extract JSON object from LLM output (handles markdown fences)."""
    import re

    # Try to find JSON in markdown code blocks first
    json_pattern = r"```(?:json)?\s*\n?(.*?)```"
    matches = re.findall(json_pattern, text, re.DOTALL)
    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue

    # Try to parse the whole thing as JSON
    text_clean = text.strip()
    # Remove leading/trailing non-JSON content
    start = text_clean.find("{")
    end = text_clean.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text_clean[start:end + 1])
        except json.JSONDecodeError:
            pass

    return None


# ── Unified parser ────────────────────────────────────────────────────────


async def parse(text: str, llm: Any | None = None) -> IntentSchema | None:
    """Parse natural language, trying template mode first, then LLM mode.

    Args:
        text: Natural language description of the workflow.
        llm: Optional LLM provider for LLM mode (required if templates don't match).

    Returns:
        IntentSchema if parsing succeeded, None otherwise.
    """
    # Try template mode first (fast path)
    schema = parse_nl(text)
    if schema is not None:
        return schema

    # Fall back to LLM mode
    if llm is not None:
        logger.info("No template matched, falling back to LLM mode")
        return await parse_nl_llm(text, llm)

    logger.warning("No template matched and no LLM provided")
    return None

# Copyright 2026 ChainForge Contributors
# ALDP — Agent Live Debug Protocol: message types and serialization.

from __future__ import annotations

import json
from enum import Enum
from typing import Any


class ALDPMessageType(str, Enum):
    state = "state"
    tool_call = "tool_call"
    tool_result = "tool_result"
    llm_response = "llm_response"
    paused = "paused"
    resumed = "resumed"
    error = "error"
    done = "done"
    breakpoint_hit = "breakpoint_hit"
    pause = "pause"
    resume = "resume"
    step_over = "step_over"
    get_state = "get_state"
    set_breakpoint = "set_breakpoint"
    remove_breakpoint = "remove_breakpoint"


def encode_event(event_type: str, data: dict[str, Any]) -> bytes:
    return json.dumps({"event": event_type, "data": data}).encode("utf-8")


def decode_message(data: bytes) -> dict[str, Any]:
    return json.loads(data.decode("utf-8"))


def event_state(state: str, iteration: int = 0, **extra) -> bytes:
    return encode_event("state", {"state": state, "iteration": iteration, **extra})

def event_tool_call(name: str, args: dict, tool_call_id: str = "") -> bytes:
    return encode_event("tool_call", {"name": name, "args": args, "id": tool_call_id})

def event_tool_result(name: str, content: str, is_error: bool = False) -> bytes:
    return encode_event("tool_result", {"name": name, "content": content, "is_error": is_error})

def event_llm_response(content: str) -> bytes:
    return encode_event("llm_response", {"content": content})

def event_paused(breakpoint: str, snapshot: dict | None = None) -> bytes:
    return encode_event("paused", {"breakpoint": breakpoint, "snapshot": snapshot or {}})

def event_resumed() -> bytes:
    return encode_event("resumed", {})

def event_done(output: str = "") -> bytes:
    return encode_event("done", {"output": output})

def event_error(message: str) -> bytes:
    return encode_event("error", {"message": message})


__all__ = [
    "ALDPMessageType", "encode_event", "decode_message",
    "event_state", "event_tool_call", "event_tool_result",
    "event_llm_response", "event_paused", "event_resumed",
    "event_done", "event_error",
]

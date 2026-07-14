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
"""A2A (Agent-to-Agent) protocol type definitions.

Implements the core data models from Google's Agent-to-Agent (A2A) protocol spec.
https://github.com/google/A2A
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Task State Machine ──────────────────────────────────────────────────────


class TaskState(str, Enum):
    """Lifecycle states of an A2A task."""
    submitted = "submitted"
    working = "working"
    input_required = "input-required"
    completed = "completed"
    failed = "failed"
    canceled = "canceled"


class TaskStatus(BaseModel):
    """Current status of a task including state, message, and timestamp."""
    state: TaskState = Field(description="Current task state")
    message: Message | None = Field(default=None, description="Optional human-readable status message")
    timestamp: str = Field(default="", description="ISO 8601 timestamp")


# ── Parts (content units within Messages / Artifacts) ──────────────────────


class FileContent(BaseModel):
    """A file reference (name, mime type, and bytes/data)."""
    name: str | None = Field(default=None, description="File name")
    mime_type: str | None = Field(default=None, description="MIME type of the file")
    bytes: str | None = Field(default=None, description="Base64-encoded file content")
    uri: str | None = Field(default=None, description="URI to the file content")


class Part(BaseModel):
    """A single piece of content within a Message or Artifact."""
    text: str | None = Field(default=None, description="Text content")
    file: FileContent | None = Field(default=None, description="File content")
    data: dict[str, Any] | None = Field(default=None, description="Structured data (JSON)")


# ── Message ────────────────────────────────────────────────────────────────


class Message(BaseModel):
    """A message exchanged between agents or between client and agent."""
    role: str = Field(default="agent", description="Role of the message sender (agent, user, system)")
    parts: list[Part] = Field(default_factory=list, description="Content parts of the message")
    metadata: dict[str, Any] | None = Field(default=None, description="Arbitrary metadata")


# ── Artifact ───────────────────────────────────────────────────────────────


class Artifact(BaseModel):
    """An artifact produced during task execution."""
    name: str | None = Field(default=None, description="Artifact name")
    description: str | None = Field(default=None, description="Artifact description")
    parts: list[Part] = Field(default_factory=list, description="Content parts")
    metadata: dict[str, Any] | None = Field(default=None, description="Arbitrary metadata")
    index: int = Field(default=0, description="Index of this artifact in the sequence")
    append: bool | None = Field(default=None, description="Whether this artifact appends to previous at same index")


# ── Task ───────────────────────────────────────────────────────────────────


class Task(BaseModel):
    """A unit of work managed by an A2A agent."""
    id: str = Field(description="Unique task identifier")
    session_id: str | None = Field(default=None, description="Optional session grouping identifier")
    status: TaskStatus = Field(description="Current task status")
    history: list[Message] = Field(default_factory=list, description="Full message history of the task")
    artifacts: list[Artifact] = Field(default_factory=list, description="Artifacts produced by the task")
    metadata: dict[str, Any] | None = Field(default=None, description="Arbitrary metadata")


# ── Skill (Agent capability description) ──────────────────────────────────


class Skill(BaseModel):
    """A capability or skill that an agent advertises."""
    id: str = Field(description="Unique skill identifier")
    name: str = Field(description="Human-readable skill name")
    description: str | None = Field(default=None, description="Skill description")
    tags: list[str] = Field(default_factory=list, description="Tags for discovery")
    examples: list[str] = Field(default_factory=list, description="Example prompts")
    input_modes: list[str] = Field(default_factory=lambda: ["text"], description="Accepted input content modes")
    output_modes: list[str] = Field(default_factory=lambda: ["text"], description="Output content modes")


# ── Agent Card ─────────────────────────────────────────────────────────────


class AgentAuthentication(BaseModel):
    """Authentication scheme for an agent."""
    schemes: list[str] = Field(default_factory=lambda: ["bearer"], description="Supported auth schemes")
    credentials: str | None = Field(default=None, description="Credential hint / location")


class AgentCapabilities(BaseModel):
    """Capabilities the agent supports."""
    streaming: bool = Field(default=False, description="Supports SSE streaming")
    push_notifications: bool = Field(default=False, description="Supports push notifications")
    input_modes: list[str] = Field(default_factory=lambda: ["text"], description="Default input modes")
    output_modes: list[str] = Field(default_factory=lambda: ["text"], description="Default output modes")


class AgentProvider(BaseModel):
    """Organization providing the agent."""
    name: str | None = Field(default=None, description="Provider name")
    url: str | None = Field(default=None, description="Provider URL")


class AgentCard(BaseModel):
    """An agent's 'business card' — advertised capabilities and identity."""
    name: str = Field(description="Agent name")
    description: str | None = Field(default=None, description="Agent description")
    url: str = Field(default="", description="Agent endpoint URL")
    provider: AgentProvider | None = Field(default=None, description="Provider info")
    version: str = Field(default="1.0", description="Agent specification version")
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities, description="Agent capabilities")
    skills: list[Skill] = Field(default_factory=list, description="Advertised skills")
    authentication: AgentAuthentication | None = Field(default=None, description="Auth requirements")
    default_input_modes: list[str] = Field(default_factory=lambda: ["text"], description="Default accepted input modes")
    default_output_modes: list[str] = Field(default_factory=lambda: ["text"], description="Default output modes")


# ── Request / Response Types ───────────────────────────────────────────────


class PushNotificationConfig(BaseModel):
    """Configuration for push notifications."""
    url: str = Field(description="URL to send push updates to")
    authentication: AgentAuthentication | None = Field(default=None, description="Auth for push endpoint")


class TaskSendParams(BaseModel):
    """Parameters for sending a task to an agent."""
    id: str = Field(description="Client-generated task ID")
    session_id: str | None = Field(default=None, description="Session grouping ID")
    message: Message = Field(description="The initial message or continuation input")
    push_notification: PushNotificationConfig | None = Field(default=None, description="Optional push config")
    history_length: int | None = Field(default=None, description="Number of history messages to return")
    metadata: dict[str, Any] | None = Field(default=None, description="Arbitrary metadata")


class TaskSendResult(BaseModel):
    """Result of a task-send operation."""
    task: Task = Field(description="The updated task object")


class TaskQuery(BaseModel):
    """Query to get current task state."""
    id: str = Field(description="Task ID to query")
    history_length: int | None = Field(default=None, description="Number of history items to include")


class TaskGetResult(BaseModel):
    """Result of a task-get operation."""
    task: Task = Field(description="The current task state")


class TaskCancelResult(BaseModel):
    """Result of a task-cancel operation."""
    task: Task = Field(description="The canceled task")


class TaskIdResubscribeParams(BaseModel):
    """Parameters for resubscribing to a completed task."""
    id: str = Field(description="Task ID to resubscribe to")
    history_length: int | None = Field(default=None, description="Number of history items to include")


# ── Error Handling ─────────────────────────────────────────────────────────


class A2AError(BaseModel):
    """A2A protocol error."""
    code: int = Field(description="Error code")
    message: str = Field(description="Error message")
    data: dict[str, Any] | None = Field(default=None, description="Additional error data")


class A2AResponse(BaseModel):
    """Standard A2A JSON-RPC response wrapper."""
    id: str = Field(default="", description="Request ID")
    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")
    result: dict[str, Any] | None = Field(default=None, description="Result payload")
    error: A2AError | None = Field(default=None, description="Error info")


# ── Helper factory functions ───────────────────────────────────────────────


def make_message(role: str, text: str, **kwargs) -> Message:
    """Create a simple text message."""
    return Message(role=role, parts=[Part(text=text)], **kwargs)


def make_user_message(text: str) -> Message:
    """Create a user message."""
    return make_message("user", text)


def make_agent_message(text: str) -> Message:
    """Create an agent message."""
    return make_message("agent", text)


def make_system_message(text: str) -> Message:
    """Create a system message."""
    return make_message("system", text)


def make_artifact(name: str, text: str, **kwargs) -> Artifact:
    """Create a simple text artifact."""
    return Artifact(name=name, parts=[Part(text=text)], **kwargs)


def make_task(
    task_id: str,
    state: TaskState = TaskState.submitted,
    history: list[Message] | None = None,
    **kwargs,
) -> Task:
    """Create a task with the given state and history."""
    import datetime
    return Task(
        id=task_id,
        status=TaskStatus(
            state=state,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        ),
        history=history or [],
        **kwargs,
    )

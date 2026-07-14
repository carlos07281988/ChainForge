"""Agent-to-Agent (A2A) protocol support.

Implements Google's A2A protocol for standardized agent communication.
https://github.com/google/A2A

Core exports:
  - AgentCard, Skill, AgentCapabilities — agent advertisement
  - Task, TaskState, Message, Part, Artifact — task model
  - A2ARouter — protocol server (FastAPI)
  - A2AClient — protocol client
  - A2AAgentProxy — remote agent as local proxy
  - build_agent_card() — build AgentCard from ChainForge Agent
  - mount_a2a() — mount into existing FastAPI app
"""

from chainforge.a2a.types import (
    A2AError,
    A2AResponse,
    AgentAuthentication,
    AgentCapabilities,
    AgentCard,
    AgentProvider,
    Artifact,
    FileContent,
    Message,
    Part,
    PushNotificationConfig,
    Skill,
    Task,
    TaskCancelResult,
    TaskGetResult,
    TaskIdResubscribeParams,
    TaskQuery,
    TaskSendParams,
    TaskSendResult,
    TaskState,
    TaskStatus,
    make_agent_message,
    make_artifact,
    make_message,
    make_system_message,
    make_task,
    make_user_message,
)

from chainforge.a2a.card import build_agent_card
from chainforge.a2a.server import A2ARouter, A2AAgentWrapper, TaskStore, create_a2a_app
from chainforge.a2a.client import A2AClient, A2AAgentProxy
from chainforge.a2a.integration import mount_a2a

__all__ = [
    "A2AError",
    "A2AResponse",
    "AgentAuthentication",
    "AgentCapabilities",
    "AgentCard",
    "AgentProvider",
    "Artifact",
    "FileContent",
    "Message",
    "Part",
    "PushNotificationConfig",
    "Skill",
    "Task",
    "TaskCancelResult",
    "TaskGetResult",
    "TaskIdResubscribeParams",
    "TaskQuery",
    "TaskSendParams",
    "TaskSendResult",
    "TaskState",
    "TaskStatus",
    "make_agent_message",
    "make_artifact",
    "make_message",
    "make_system_message",
    "make_task",
    "make_user_message",
    "build_agent_card",
    "A2ARouter",
    "A2AAgentWrapper",
    "TaskStore",
    "create_a2a_app",
    "A2AClient",
    "A2AAgentProxy",
    "mount_a2a",
]

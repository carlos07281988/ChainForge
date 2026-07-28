# Copyright 2026 ChainForge Contributors. Apache 2.0.
"""Experience — data model for shared agent experiences."""
from __future__ import annotations
from pydantic import BaseModel, Field

class Experience(BaseModel):
    """A single shared experience from an agent execution."""
    id: str = Field(description="Unique experience identifier")
    task: str = Field(default="", description="Summary of the user request")
    task_type: str = Field(default="general", description="refund_request, qa, code_gen, etc.")
    tools_used: list[str] = Field(default_factory=list)
    model_used: str = Field(default="unknown")
    outcome: str = Field(default="unknown", description="success | failure | partial")
    feedback: str | None = Field(default=None, description="Optional human feedback")
    cost: float = Field(default=0.0)
    tokens: int = Field(default=0)
    duration_ms: float = Field(default=0.0)
    timestamp: float = Field(default=0.0)
    decay_factor: float = Field(default=1.0, description="Current decay multiplier (1.0 = fresh)")

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
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field
import time
import uuid

from chainforge.enterprise.durable.checkpoint import Checkpoint


class JobStatus(BaseModel):
    job_id: str
    agent_id: str
    status: str = "queued"
    progress: float = 0.0
    created_at: float = Field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    last_checkpoint_at: float | None = None
    result: Any = None
    error: str | None = None


class JobHandle(BaseModel):
    job_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_id: str = ""
    prompt: str = ""
    status: str = "queued"  # queued|running|checkpointing|done|failed|cancelled
    progress: float = 0.0  # 0.0 - 1.0
    created_at: float = Field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    last_checkpoint_at: float | None = None
    result: Any = None
    error: str | None = None
    checkpoints: list[Checkpoint] = Field(default_factory=list)

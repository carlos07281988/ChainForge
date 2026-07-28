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
from pydantic import BaseModel, Field


class CrashRecoveryPolicy(BaseModel):
    """Policy for how to handle job recovery after a crash."""
    auto_retry: bool = Field(default=True, description="Automatically resume incomplete jobs on startup")
    max_retries: int = Field(default=3, ge=0, le=10)
    resume_from: str = Field(default="last_checkpoint", description="last_checkpoint | restart")
    backoff_seconds: float = Field(default=5.0, description="Delay before auto-retry")

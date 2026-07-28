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
"""LoRA adapter configuration for distilled student models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from chainforge.logging import get_logger

logger = get_logger("enterprise.distill.adapter")


class LoRAConfig(BaseModel):
    """LoRA fine-tuning configuration."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    r: int = Field(default=16, ge=1, le=256)
    alpha: int = Field(default=32, ge=1, le=512)
    target_modules: list[str] = Field(
        default_factory=lambda: ["q_proj", "v_proj", "k_proj", "o_proj"]
    )
    dropout: float = 0.05
    bias: str = "none"


class LoRAAdapter(BaseModel):
    """Adapter for LoRA fine-tuning of distilled student models.

    This is a configuration layer — actual training is delegated to
    external frameworks (unsloth, transformers, vllm). ChainForge provides
    the training data and LoRA config; the framework does the rest.

    Usage:
        adapter = LoRAAdapter(config=LoRAConfig(r=16, alpha=32))
        config_dict = adapter.to_framework("unsloth")
        # → passes this dict to Unsloth's FastLanguageModel.get_peft_model()
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    config: LoRAConfig = Field(default_factory=LoRAConfig)
    base_model: str = Field(default="qwen2.5-3b")

    def to_framework(self, framework: str = "unsloth") -> dict[str, Any]:
        """Export LoRA config in framework-specific format."""
        if framework == "unsloth":
            return {
                "r": self.config.r,
                "lora_alpha": self.config.alpha,
                "target_modules": self.config.target_modules,
                "lora_dropout": self.config.dropout,
                "bias": self.config.bias,
            }
        elif framework == "transformers":
            return {
                "r": self.config.r,
                "lora_alpha": self.config.alpha,
                "target_modules": self.config.target_modules,
                "lora_dropout": self.config.dropout,
                "bias": self.config.bias,
                "task_type": "CAUSAL_LM",
            }
        elif framework == "vllm":
            return {
                "max_lora_rank": self.config.r,
                "max_loras": 1,
                "fully_sharded_loras": True,
            }
        return self.config.model_dump()

    def estimate_vram(self, precision: str = "bf16") -> dict:
        """Estimate VRAM requirements for this LoRA config."""
        base_vram = {
            "qwen2.5-3b": 6,
            "qwen2.5-7b": 14,
            "llama-3.2-3b": 6,
            "llama-3.1-8b": 16,
        }
        base_gb = base_vram.get(self.base_model, 10)
        lora_overhead = self.config.r * 0.02
        return {
            "base_model_vram_gb": base_gb,
            "lora_adapter_vram_gb": round(lora_overhead, 2),
            "total_vram_gb": round(base_gb + lora_overhead, 2),
            "precision": precision,
        }

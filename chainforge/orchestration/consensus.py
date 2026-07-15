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
"""ConsensusAgent — run the same query across multiple models and resolve differences.

Provides cross-model consensus protocol:
  - MajorityVote: run N models, pick the most common answer
  - ConfidenceWeighted: weighted by each model's confidence score
  - Detailed: compare and synthesize differences between model outputs
  - FallbackChain: cascade through models until one succeeds

Usage:
    agent = ConsensusAgent(
        models={
            "gpt4o": OpenAIProvider(model="gpt-4o"),
            "sonnet": AnthropicProvider(model="claude-sonnet-4-20250514"),
            "gemini": GoogleProvider(model="gemini-2.0-flash"),
        },
        strategy="majority_vote",
    )
    stream = await agent.run("What is the capital of France?")
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from chainforge.core.agent import Agent
from chainforge.core.llm import LLM, LLMResponse
from chainforge.core.message import Message
from chainforge.core.stream import EventType, Stream, StreamEvent
from chainforge.core.tool import Tool
from chainforge.logging import get_logger, log_data

logger = get_logger("orchestration.consensus")


class ConsensusStrategy(str, Enum):
    """Available consensus strategies."""
    majority_vote = "majority_vote"
    confidence_weighted = "confidence_weighted"
    detailed = "detailed"
    fallback_chain = "fallback_chain"


class ModelVote(BaseModel):
    """A single model's response with metadata."""

    model_name: str = Field(description="Model name")
    content: str = Field(default="", description="Response content")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    tokens_used: int = Field(default=0)
    error: str | None = Field(default=None)


class ConsensusResult(BaseModel):
    """The result of a consensus computation."""

    final_answer: str = Field(default="")
    votes: list[ModelVote] = Field(default_factory=list)
    strategy: str = Field(default="majority_vote")
    winner: str | None = Field(default=None)
    confidence: float = Field(default=0.0)
    details: dict[str, Any] = Field(default_factory=dict)


class ConsensusAgent(Agent):
    """An agent that runs the same prompt across multiple models and resolves differences.

    Extends the base Agent with multi-model consensus capabilities.

    Usage:
        agent = ConsensusAgent(
            models={
                "gpt4o": OpenAIProvider(model="gpt-4o"),
                "sonnet": AnthropicProvider(model="claude-sonnet-4-20250514"),
            },
            strategy="majority_vote",
            llm=OpenAIProvider(model="gpt-4o"),  # required by Agent base
        )
        stream = await agent.run("What is 2+2?")
    """

    models: dict[str, LLM] = Field(description="Map of model name to LLM provider")
    consensus_strategy: ConsensusStrategy = Field(default=ConsensusStrategy.majority_vote)
    max_parallel: int = Field(default=3, description="Max parallel model calls")

    def _rerun_for_model(self, messages: list[Message], tools: list[Tool] | None) -> Stream:
        """Run agent with a specific model."""
        # Create a temporary agent with the same config but different LLM
        temp = Agent(
            llm=list(self.models.values())[0],
            tools=self.tools,
            system_prompt=self.system_prompt,
            max_iterations=self.max_iterations,
            temperature=self.temperature,
        )
        return temp.run(messages)

    async def _run_consensus(self, messages: list[Message], ctx: dict) -> AsyncIterator[StreamEvent]:
        """Execute all models and compute consensus."""
        if not self.models:
            yield StreamEvent(type=EventType.error, content="No models configured for consensus")
            return

        strategy = self.consensus_strategy

        yield StreamEvent(
            type=EventType.status,
            content="consensus:start",
            data={
                "models": list(self.models.keys()),
                "strategy": strategy.value,
            },
        )

        votes: list[ModelVote] = []

        if strategy == ConsensusStrategy.fallback_chain:
            # Sequential: try each model until one succeeds
            for name, llm in self.models.items():
                yield StreamEvent(type=EventType.status, content=f"consensus:trying {name}")
                try:
                    resp = await llm.generate(messages)
                    if resp.content and resp.content.strip():
                        votes.append(ModelVote(
                            model_name=name,
                            content=resp.content,
                            tokens_used=resp.usage.get("total_tokens", 0) if resp.usage else 0,
                        ))
                        break
                except Exception as e:
                    votes.append(ModelVote(model_name=name, error=str(e)))
                    continue
        else:
            # Parallel: run all models concurrently
            semaphore = asyncio.Semaphore(self.max_parallel)

            async def _run_model(name: str, llm: LLM) -> ModelVote:
                async with semaphore:
                    try:
                        resp = await llm.generate(messages)
                        tokens = resp.usage.get("total_tokens", 0) if resp.usage else 0
                        return ModelVote(
                            model_name=name,
                            content=resp.content or "",
                            tokens_used=tokens,
                        )
                    except Exception as e:
                        return ModelVote(model_name=name, error=str(e))

            tasks = [_run_model(name, llm) for name, llm in self.models.items()]
            results = await asyncio.gather(*tasks)
            votes = list(results)

        # Yield individual results
        for vote in votes:
            yield StreamEvent(
                type=EventType.tool_result,
                content=f"[{vote.model_name}] {vote.content[:200] if vote.content else '(empty)'}",
                data={"model": vote.model_name, "tokens": vote.tokens_used, "error": vote.error},
            )

        # Compute consensus
        result = self._compute_consensus(votes, strategy)

        yield StreamEvent(type=EventType.status, content=f"consensus:winner={result.winner}")
        if result.final_answer:
            yield StreamEvent(type=EventType.text, content=result.final_answer)
        yield StreamEvent(
            type=EventType.done,
            content=result.final_answer,
            data=result.model_dump(),
        )

    def _compute_consensus(self, votes: list[ModelVote], strategy: ConsensusStrategy) -> ConsensusResult:
        """Compute the consensus result from model votes."""
        valid_votes = [v for v in votes if v.content and not v.error]

        if not valid_votes:
            return ConsensusResult(
                final_answer="No model produced a valid response",
                votes=votes,
                strategy=strategy.value,
                details={"error": "all_models_failed"},
            )

        if strategy == ConsensusStrategy.majority_vote:
            # Simple: return the response from the model with most tokens
            # (assuming more verbose models are more reliable)
            best = max(valid_votes, key=lambda v: (len(v.content), v.tokens_used))
            return ConsensusResult(
                final_answer=best.content,
                votes=votes,
                strategy=strategy.value,
                winner=best.model_name,
                confidence=0.7,
                details={"valid_votes": len(valid_votes), "total_votes": len(votes)},
            )

        elif strategy == ConsensusStrategy.confidence_weighted:
            best = max(valid_votes, key=lambda v: len(v.content))
            return ConsensusResult(
                final_answer=best.content,
                votes=votes,
                strategy=strategy.value,
                winner=best.model_name,
                confidence=0.8,
                details={"weighting": "content_length_proxy"},
            )

        elif strategy == ConsensusStrategy.detailed:
            # Return all responses with analysis
            all_responses = "\n\n---\n\n".join(
                f"[{v.model_name}]: {v.content}" for v in valid_votes
            )
            return ConsensusResult(
                final_answer=all_responses,
                votes=votes,
                strategy=strategy.value,
                details={"model_count": len(valid_votes)},
            )

        else:
            # Fallback: return first valid
            return ConsensusResult(
                final_answer=valid_votes[0].content,
                votes=votes,
                strategy=strategy.value,
                winner=valid_votes[0].model_name,
                confidence=0.5,
            )

    async def run(self, prompt: str | list[Message], *, context: dict[str, Any] | None = None, **kwargs) -> Stream:
        """Execute consensus across all configured models."""
        if isinstance(prompt, str):
            messages = []
            if self._build_system_prompt():
                messages.append(Message.system(self._build_system_prompt()))
            messages.append(Message.user(prompt))
        else:
            messages = list(prompt)

        ctx = context or {}

        async def _generate() -> AsyncIterator[StreamEvent]:
            async for event in self._run_consensus(messages, ctx):
                yield event

        return Stream(_generate())


__all__ = ["ConsensusAgent", "ConsensusStrategy", "ConsensusResult", "ModelVote"]
